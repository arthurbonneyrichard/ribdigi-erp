"""RIBDIGI till print agent.

Collects this till's print jobs from the ERP and sends them straight to the
thermal printer: no browser, no print dialog. A job is reported printed only
when the printer (or the Windows print queue) accepted it.

Commands:
  python agent.py pair CODE ["Till name"]   pair once; shows the token once
  python agent.py                            run the agent
  python agent.py test "windows:XP-80"       print a test slip, no ERP needed
  python agent.py journal                    only the local offline listener

Environment (do not commit .env):
  RIBDIGI_API_BASE     e.g. https://erp.example.com/api/v1
  RIBDIGI_AGENT_TOKEN  shown once at pairing (rdp_...)
  RIBDIGI_PRINTER      default printer when the ERP names none (see printing.py)
  RIBDIGI_WEB_ORIGIN   web address of the ERP, if it differs from the API address,
                       so the till page may print through this agent when offline

--dry-run prints the text to this window and reports nothing as printed.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

import local_print
import printing

API = os.environ.get("RIBDIGI_API_BASE", "http://localhost:8000/api/v1").rstrip("/")
TOKEN = os.environ.get("RIBDIGI_AGENT_TOKEN", "")
# About one second, so paper keeps pace with the screen. Slows down while the ERP is unreachable.
POLL_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 10.0


def request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"X-Print-Agent-Token": TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pair(code: str, label: str = "Till") -> str:
    payload = json.dumps({"pairing_code": code, "label": label}).encode("utf-8")
    req = urllib.request.Request(
        API + "/printers/agents/pair",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = (body.get("data") or {}).get("agent_token")
    if not token:
        raise SystemExit("Pairing succeeded but no token was returned")
    print("Store this token in RIBDIGI_AGENT_TOKEN. It will not be shown again.", file=sys.stderr)
    print(token)
    return token


def print_job(job: dict, *, dry_run: bool = False) -> tuple[str, str]:
    """Print one claimed job. Returns the status and detail to report."""
    target = job.get("target")
    local = False
    if not target:
        target = os.environ.get("RIBDIGI_PRINTER", "").strip()
        local = True
    encoded = job.get("escpos_base64")
    if dry_run:
        print((job.get("payload") or {}).get("text") or "(no text)")
        return "failed", "dry run: nothing was sent to a printer"
    if not encoded:
        return "failed", "This job has nothing to print"
    if not target:
        return "failed", "No printer is set up for this till (set one in Printers, or RIBDIGI_PRINTER)"
    data = base64.b64decode(encoded)
    copies = max(1, min(9, int(job.get("copies") or 1)))
    try:
        for _ in range(copies):
            printing.send(target, data, local=local)
    except printing.PrintError as exc:
        return "failed", str(exc)
    if job.get("purpose") == "customer_receipt":
        local_print.remember_receipt_printer(target, local=local)
    return "printed", "accepted by the printer"


class Runner:
    """Claim, print once, report. A report that cannot be sent is kept and sent again;
    the job is not printed a second time."""

    def __init__(self, send=request, dry_run: bool = False):
        self.send = send
        self.dry_run = dry_run
        self.unreported: dict[str, dict] = {}

    def _report(self, job_id: str) -> None:
        try:
            self.send(f"/printers/agent/jobs/{job_id}/complete", method="POST", body=self.unreported[job_id])
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 404, 409):
                raise
            print(f"job {job_id} can no longer be reported (HTTP {exc.code})", file=sys.stderr)
        self.unreported.pop(job_id, None)

    def once(self) -> int:
        for job_id in list(self.unreported):
            self._report(job_id)
        jobs = self.send("/printers/agent/jobs?limit=10").get("data") or []
        for job in jobs:
            status, detail = print_job(job, dry_run=self.dry_run)
            print(f"job {job['id']} {job.get('purpose')}: {status} ({detail})", file=sys.stderr)
            self.unreported[job["id"]] = {"status": status, "detail": detail[:200]}
        for job_id in list(self.unreported):
            self._report(job_id)
        return len(jobs)


def loop(dry_run: bool = False) -> None:
    if not TOKEN:
        raise SystemExit('Set RIBDIGI_AGENT_TOKEN or run: python agent.py pair CODE')
    runner = Runner(dry_run=dry_run)
    wait = POLL_SECONDS
    while True:
        try:
            runner.once()
            wait = POLL_SECONDS
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read()[:200]!r}", file=sys.stderr)
            wait = min(MAX_BACKOFF_SECONDS, wait * 2)
        except Exception as exc:  # noqa: BLE001 - keep serving the till
            print(f"poll error: {exc}", file=sys.stderr)
            wait = min(MAX_BACKOFF_SECONDS, wait * 2)
        time.sleep(wait)


def test_print(target: str) -> None:
    text = "RIBDIGI test print\r\nThis is not a sale.\r\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\r\n"
    data = b"\x1b\x40" + text.encode("ascii") + b"\x1b\x64\x05\x1d\x56\x00"
    try:
        printing.send(target, data, local=True)
    except printing.PrintError as exc:
        raise SystemExit(f"Test print failed: {exc}")
    print("The printer accepted the test slip. Check that paper came out.")


def _start_journal() -> None:
    from journal import serve_forever, serve_in_thread

    if len(sys.argv) >= 2 and sys.argv[1] == "journal":
        serve_forever()
        return
    try:
        serve_in_thread()
    except OSError as exc:
        print(f"offline sale journal not listening: {exc}", file=sys.stderr)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if args[:1] == ["journal"]:
        _start_journal()
    elif args[:1] == ["pair"] and len(args) >= 2:
        pair(args[1], args[2] if len(args) > 2 else "Till")
    elif args[:1] == ["test"] and len(args) >= 2:
        test_print(args[1])
    else:
        _start_journal()
        loop(dry_run=dry)
