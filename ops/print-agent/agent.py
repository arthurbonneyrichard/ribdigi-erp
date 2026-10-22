"""RIBDIGI till print agent (stub).

Polls the tenant API for queued jobs and writes them to stdout / a file.
This does not talk to a physical printer. Install on the till, pair with a
one-time code from Company Admin → Printers.

Environment (do not commit .env):
  RIBDIGI_API_BASE   e.g. https://erp.example.com/api/v1
  RIBDIGI_AGENT_TOKEN  shown once at pairing (rdp_...)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("RIBDIGI_API_BASE", "http://localhost:8000/api/v1").rstrip("/")
TOKEN = os.environ.get("RIBDIGI_AGENT_TOKEN", "")


def request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "X-Print-Agent-Token": TOKEN,
            "Content-Type": "application/json",
        },
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


def loop() -> None:
    if not TOKEN:
        raise SystemExit("Set RIBDIGI_AGENT_TOKEN or run: python agent.py pair CODE")
    while True:
        try:
            body = request("/printers/agent/jobs?limit=10")
            jobs = body.get("data") or []
            for job in jobs:
                text = ((job.get("payload") or {}).get("text")) or json.dumps(job)
                print(f"--- job {job.get('id')} {job.get('purpose')} ---")
                print(text)
                request(
                    f"/printers/agent/jobs/{job['id']}/complete",
                    method="POST",
                    body={"status": "printed", "detail": "stub agent (no hardware)"},
                )
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read()[:200]!r}", file=sys.stderr)
        except Exception as exc:
            print(f"poll error: {exc}", file=sys.stderr)
        time.sleep(3)


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
    if len(sys.argv) >= 2 and sys.argv[1] == "journal":
        _start_journal()
    elif len(sys.argv) >= 3 and sys.argv[1] == "pair":
        pair(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Till")
    else:
        _start_journal()
        loop()
