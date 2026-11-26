"""The till print agent against an emulated network printer (a local TCP socket).

This proves the bytes that leave the till and the honesty of the reported status.
It does not prove that paper comes out of a physical printer.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[2] / "ops" / "print-agent"
sys.path.insert(0, str(AGENT_DIR))

import agent  # noqa: E402
import journal  # noqa: E402
import local_print  # noqa: E402
import printing  # noqa: E402

SLIP = b"\x1b\x40Demo Mart\r\nTOTAL 20.00\r\n\x1d\x56\x00"


class FakePrinter:
    """Accepts raw bytes like a port-9100 printer and can answer DLE EOT status."""

    def __init__(self, status: dict[int, int] | None = None):
        self.status = status or {}
        self.received: list[bytes] = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.done = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            data = b""
            with conn:
                while chunk := conn.recv(4096):
                    if len(chunk) == 3 and chunk[:2] == b"\x10\x04":
                        if chunk[2] in self.status:
                            conn.sendall(bytes((self.status[chunk[2]],)))
                        continue
                    data += chunk
            if data:
                self.received.append(data)
            self.done.set()


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("RIBDIGI_PRINT_STATE", str(tmp_path / "print-state.json"))
    monkeypatch.delenv("RIBDIGI_PRINTER", raising=False)
    monkeypatch.setenv("RIBDIGI_API_BASE", "https://erp.example.com/api/v1")


def _job(target, **extra):
    return {
        "id": "job-1",
        "purpose": "customer_receipt",
        "target": target,
        "copies": 1,
        "escpos_base64": base64.b64encode(SLIP).decode(),
        "payload": {"text": "Demo Mart"},
        **extra,
    }


def test_network_printer_receives_the_exact_bytes():
    printer = FakePrinter()
    status, _ = agent.print_job(_job(f"tcp:127.0.0.1:{printer.port}"))
    assert status == "printed"
    assert printer.done.wait(3)
    assert printer.received == [SLIP]


def test_out_of_paper_is_not_printed():
    printer = FakePrinter(status={1: 0x12, 4: 0x72})
    status, detail = agent.print_job(_job(f"tcp:127.0.0.1:{printer.port}"))
    assert status == "failed" and "paper" in detail
    assert printer.done.wait(3)
    assert printer.received == []


def test_offline_printer_unreachable_dry_run_and_no_printer_are_never_printed():
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()
    assert agent.print_job(_job(f"tcp:127.0.0.1:{port}"))[0] == "failed"
    assert agent.print_job(_job("tcp:8.8.8.8:9100")) == ("failed", "The printer must be on this shop's own network")
    assert agent.print_job(_job("tcp:127.0.0.1:9100"), dry_run=True)[0] == "failed"
    assert agent.print_job(_job(None))[0] == "failed"
    # A device file may only come from the till's own settings, never from the server.
    assert agent.print_job(_job("file:/tmp/anything"))[0] == "failed"


def test_windows_spooler_states():
    assert printing.job_state(0x80) == (True, None)
    assert printing.job_state(0x20) == (False, "The printer is offline")
    assert printing.job_state(0x10) == (False, None)


def test_lost_report_is_resent_without_printing_twice(monkeypatch):
    printed: list[str] = []
    monkeypatch.setattr(printing, "send", lambda target, data, local=False: printed.append(target))
    queue = [[_job("tcp:192.168.1.130:9100")], []]
    reports: list[dict] = []
    broken = {"on": True}

    def send(path, method="GET", body=None):
        if path.startswith("/printers/agent/jobs?"):
            return {"data": queue.pop(0) if queue else []}
        if broken["on"]:
            raise urllib.error.URLError("connection dropped")
        reports.append(body)
        return {}

    runner = agent.Runner(send=send)
    with pytest.raises(urllib.error.URLError):
        runner.once()
    broken["on"] = False
    runner.once()
    assert printed == ["tcp:192.168.1.130:9100"]
    assert [r["status"] for r in reports] == ["printed"]


def test_offline_print_only_for_the_erp_page_and_once_per_receipt(monkeypatch):
    printer = FakePrinter()
    monkeypatch.setenv("RIBDIGI_PRINTER", f"tcp:127.0.0.1:{printer.port}")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), journal.JournalHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/v1/print"

    def post(origin, body, content_type="application/json"):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers={"Origin": origin, "Content-Type": content_type}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, {}

    try:
        body = {"ref": "OFF-1", "text": "Offline sale\n\x1bp\x00TOTAL 5.00"}
        assert post("https://evil.example.com", body)[0] == 403
        assert post("https://erp.example.com", body, "text/plain")[0] == 415
        assert post("https://erp.example.com", body) == (200, {"status": "printed", "duplicate": False})
        assert post("https://erp.example.com", body)[1]["duplicate"] is True
    finally:
        httpd.shutdown()
    assert printer.done.wait(3)
    assert len(printer.received) == 1
    sent = printer.received[0]
    assert b"Offline sale" in sent
    # The drawer-kick command typed into the text was neutralised.
    assert b"\x1bp\x00" not in sent


def test_offline_print_uses_the_last_receipt_printer(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(printing, "send", lambda target, data, local=False: sent.append(target))
    with pytest.raises(local_print.LocalPrintError) as none:
        local_print.handle("https://erp.example.com", {"ref": "A", "text": "x"})
    assert none.value.status == 409
    agent.print_job(_job("windows:Xprinter XP-80"))
    local_print.handle("https://erp.example.com", {"ref": "A", "text": "x"})
    assert sent == ["windows:Xprinter XP-80", "windows:Xprinter XP-80"]
