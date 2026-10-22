"""On-till copy of queued POS sales.

This file is outside the browser profile. Clearing site data (IndexedDB,
localStorage, caches) does not delete it. The till can be offline: nothing
here is uploaded.

The browser device key dies with IndexedDB, so this copy is not encrypted
with that key. Passwords, tokens, and other secrets are stripped before
the file is written. Loopback HTTP is the boundary: the server binds to
127.0.0.1 only.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ALLOWED_STATES = {"pending", "syncing", "synced", "needs_attention", "dismissed"}
SECRET_KEYS = {
    "password",
    "admin_password",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "totp_code",
    "token",
    "api_key",
    "auth_token",
    "password_enc",
    "payload_enc",
}
KEEP_FIELDS = {
    "id",
    "kind",
    "scope",
    "client_request_id",
    "local_receipt_number",
    "tenant_id",
    "store_id",
    "user_id",
    "device_id",
    "grant_id",
    "payload",
    "state",
    "retry_count",
    "last_attempt_at",
    "next_retry_at",
    "last_error_code",
    "last_error_message",
    "created_at",
    "synced_at",
    "server_sale_id",
    "server_reference",
    "sync_event_id",
    "conflict",
}
_LOCK = threading.Lock()
_MAX_BODY = 1_000_000


class JournalError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def journal_path() -> Path:
    raw = os.environ.get("RIBDIGI_OFFLINE_JOURNAL", "").strip()
    if raw:
        return Path(raw)
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if not local:
        local = str(Path.home() / ".local" / "share")
    return Path(local) / "Ribdigi" / "pos-offline-journal.json"


def journal_port() -> int:
    raw = os.environ.get("RIBDIGI_OFFLINE_PORT", "8765").strip() or "8765"
    port = int(raw)
    if port < 1 or port > 65535:
        raise JournalError(500, "RIBDIGI_OFFLINE_PORT is not a TCP port")
    return port


def scrub(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                continue
            out[str(key)] = scrub(item)
        return out
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _confirmed(record: dict[str, Any]) -> bool:
    return bool(_text(record.get("server_sale_id")) or _text(record.get("server_reference")))


def normalize_record(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JournalError(422, "Sale record must be an object")
    cleaned = scrub(raw)
    client_request_id = _text(cleaned.get("client_request_id"))
    tenant_id = _text(cleaned.get("tenant_id"))
    user_id = _text(cleaned.get("user_id"))
    if not client_request_id or not tenant_id or not user_id:
        raise JournalError(422, "client_request_id, tenant_id, and user_id are required")
    payload = cleaned.get("payload")
    if not isinstance(payload, dict):
        raise JournalError(422, "payload is required")
    state = _text(cleaned.get("state")) or "pending"
    if state not in ALLOWED_STATES:
        state = "pending"
    if state == "synced" and not _confirmed(cleaned):
        state = "pending"
    record = {key: cleaned.get(key) for key in KEEP_FIELDS if key in cleaned}
    record["client_request_id"] = client_request_id
    record["tenant_id"] = tenant_id
    record["user_id"] = user_id
    record["payload"] = payload
    record["state"] = state
    record["kind"] = "quote" if cleaned.get("kind") == "quote" else "sale"
    record["server_sale_id"] = _text(cleaned.get("server_sale_id")) or None
    record["server_reference"] = _text(cleaned.get("server_reference")) or None
    if record["state"] != "synced":
        if not _confirmed(record):
            record["server_sale_id"] = None
            record["server_reference"] = None
    return record


def _load() -> dict[str, Any]:
    path = journal_path()
    if not path.exists():
        return {"version": 1, "records": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JournalError(500, "Offline sale journal could not be read") from exc
    if not isinstance(data, dict) or not isinstance(data.get("records"), dict):
        raise JournalError(500, "Offline sale journal could not be read")
    return data


def _save(data: dict[str, Any]) -> None:
    path = journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def merge_record(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    fresh = normalize_record(incoming)
    if existing is None:
        return fresh
    if (
        existing.get("tenant_id") != fresh["tenant_id"]
        or existing.get("user_id") != fresh["user_id"]
        or existing.get("client_request_id") != fresh["client_request_id"]
    ):
        raise JournalError(409, "This sale already belongs to another company or user")
    if existing.get("state") == "synced" and _confirmed(existing):
        return dict(existing)
    merged = dict(existing)
    merged["payload"] = existing.get("payload")
    state = fresh["state"]
    if state == "synced" and not _confirmed(fresh):
        state = str(existing.get("state") or "pending")
    if state in ALLOWED_STATES:
        merged["state"] = state
    if fresh.get("server_sale_id"):
        merged["server_sale_id"] = fresh["server_sale_id"]
    if fresh.get("server_reference"):
        merged["server_reference"] = fresh["server_reference"]
    for key in (
        "synced_at",
        "last_error_code",
        "last_error_message",
        "conflict",
        "sync_event_id",
        "next_retry_at",
        "retry_count",
        "last_attempt_at",
    ):
        if key in fresh and fresh.get(key) is not None:
            merged[key] = fresh[key]
    if merged.get("state") != "synced" and not _confirmed(merged):
        merged["server_sale_id"] = None
        merged["server_reference"] = None
        merged["synced_at"] = None
    return merged


def upsert(raw: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        data = _load()
        records: dict[str, Any] = data["records"]
        incoming = normalize_record(raw)
        key = incoming["client_request_id"]
        current = records.get(key)
        if current is not None and not isinstance(current, dict):
            current = None
        merged = merge_record(current, incoming)
        records[key] = merged
        data["version"] = 1
        _save(data)
        return merged


def list_for(tenant_id: str, user_id: str) -> list[dict[str, Any]]:
    tenant = _text(tenant_id)
    user = _text(user_id)
    if not tenant or not user:
        raise JournalError(422, "tenant_id and user_id are required")
    with _LOCK:
        data = _load()
    rows = [
        row
        for row in data["records"].values()
        if isinstance(row, dict) and row.get("tenant_id") == tenant and row.get("user_id") == user
    ]
    rows.sort(key=lambda row: str(row.get("created_at") or ""))
    return rows


class JournalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/v1/offline-sales":
            self._send(404, {"error": "Not found"})
            return
        query = parse_qs(parsed.query)
        try:
            rows = list_for(
                (query.get("tenant_id") or [""])[0],
                (query.get("user_id") or [""])[0],
            )
        except JournalError as exc:
            self._send(exc.status, {"error": str(exc)})
            return
        self._send(200, {"records": rows})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/v1/offline-sales":
            self._send(404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length < 1 or length > _MAX_BODY:
            self._send(422, {"error": "Sale record is empty or too large"})
            return
        try:
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(422, {"error": "Sale record must be JSON"})
            return
        try:
            saved = upsert(raw)
        except JournalError as exc:
            self._send(exc.status, {"error": str(exc)})
            return
        self._send(
            200,
            {
                "client_request_id": saved["client_request_id"],
                "state": saved["state"],
            },
        )


def serve_forever(host: str = "127.0.0.1", port: int | None = None) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The offline sale journal listens on 127.0.0.1 only")
    chosen = journal_port() if port is None else port
    if chosen < 1 or chosen > 65535:
        raise SystemExit("RIBDIGI_OFFLINE_PORT is not a TCP port")
    httpd = ThreadingHTTPServer(("127.0.0.1", chosen), JournalHandler)
    httpd.serve_forever()


def serve_in_thread() -> threading.Thread:
    thread = threading.Thread(target=serve_forever, name="ribdigi-offline-journal", daemon=True)
    thread.start()
    return thread
