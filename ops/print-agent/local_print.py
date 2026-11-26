"""Print an offline sale from the till page, through this agent, with no print dialog.

The browser posts plain receipt text to 127.0.0.1. Only the ERP's own web address
may ask: a page from any other site is refused. Each receipt reference prints once.
The printer is RIBDIGI_PRINTER, or the one the last online receipt used.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import printing

_LOCK = threading.Lock()
MAX_TEXT = 12_000
KEPT_REFS = 500


class LocalPrintError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def state_path() -> Path:
    raw = os.environ.get("RIBDIGI_PRINT_STATE", "").strip()
    if raw:
        return Path(raw)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    return Path(base or Path.home() / ".local" / "share") / "Ribdigi" / "print-state.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def remember_receipt_printer(target: str, *, local: bool) -> None:
    with _LOCK:
        data = _load()
        if data.get("receipt_target") != target or data.get("receipt_local") != local:
            data.update(receipt_target=target, receipt_local=local)
            try:
                _save(data)
            except OSError:
                pass


def allowed_origins() -> set[str]:
    out: set[str] = set()
    for raw in (
        os.environ.get("RIBDIGI_API_BASE", "http://localhost:8000/api/v1"),
        *os.environ.get("RIBDIGI_WEB_ORIGIN", "").split(","),
    ):
        parts = urlsplit(raw.strip())
        if parts.scheme in {"http", "https"} and parts.netloc:
            out.add(f"{parts.scheme}://{parts.netloc}".lower())
    if any(o.startswith("http://localhost") for o in out):
        out.add("http://localhost:3000")
    return out


def escpos(text: str) -> bytes:
    body = text.replace("\r\n", "\n").replace("\n", "\r\n")
    # Drop control characters so page text cannot send printer commands (such as the drawer kick).
    body = "".join(ch for ch in body if ch in "\r\n" or ch >= " ")
    return b"\x1b\x40\x1b\x61\x00" + body.encode("cp437", errors="replace") + b"\x1b\x64\x05\x1d\x56\x00"


def handle(origin: str | None, raw: Any) -> dict[str, Any]:
    if (origin or "").lower() not in allowed_origins():
        raise LocalPrintError(403, "This page may not print through the till agent")
    if not isinstance(raw, dict):
        raise LocalPrintError(422, "Send a reference and the receipt text")
    ref = str(raw.get("ref") or "").strip()
    text = raw.get("text")
    if not ref or len(ref) > 120 or not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise LocalPrintError(422, "Send a reference and the receipt text")
    again = raw.get("again") is True
    with _LOCK:
        data = _load()
        done = list(data.get("printed_refs") or [])
        if ref in done and not again:
            return {"status": "printed", "duplicate": True}
        target = os.environ.get("RIBDIGI_PRINTER", "").strip()
        local = True
        if not target:
            target = str(data.get("receipt_target") or "")
            local = bool(data.get("receipt_local"))
        if not target:
            raise LocalPrintError(409, "No receipt printer is known on this till yet. Set RIBDIGI_PRINTER")
        try:
            printing.send(target, escpos(text), local=local)
        except printing.PrintError as exc:
            raise LocalPrintError(502, str(exc)) from exc
        data["printed_refs"] = ([x for x in done if x != ref] + [ref])[-KEPT_REFS:]
        _save(data)
    return {"status": "printed", "duplicate": False}
