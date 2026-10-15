"""Till-agent journal: the copy that survives a cleared browser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops" / "print-agent"))

import journal  # noqa: E402


@pytest.fixture
def journal_file(tmp_path, monkeypatch):
    path = tmp_path / "pos-offline-journal.json"
    monkeypatch.setenv("RIBDIGI_OFFLINE_JOURNAL", str(path))
    return path


def test_cleared_browser_copy_keeps_the_same_sale(journal_file):
    journal.upsert(
        {
            "client_request_id": "cr-keep",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "pending",
            "password": "secret",
            "payload": {
                "total": 12.5,
                "items": [{"product_id": "p1", "unit_price": 10, "quantity": 1}],
                "password": "nope",
            },
        }
    )
    journal.upsert(
        {
            "client_request_id": "cr-keep",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "synced",
            "payload": {"total": 99, "items": [{"unit_price": 1}]},
        }
    )
    rows = journal.list_for("t1", "u1")
    assert len(rows) == 1
    assert rows[0]["client_request_id"] == "cr-keep"
    assert rows[0]["state"] == "pending"
    assert rows[0]["payload"]["total"] == 12.5
    assert rows[0]["payload"]["items"][0]["unit_price"] == 10
    assert journal.list_for("t2", "u1") == []
    assert journal.list_for("t1", "someone-else") == []
    raw = journal_file.read_text(encoding="utf-8")
    assert "cr-keep" in raw
    assert "secret" not in raw
    assert "nope" not in raw
    stored = json.loads(raw)
    assert stored["records"]["cr-keep"]["client_request_id"] == "cr-keep"


def test_server_confirmation_marks_synced_without_changing_terms(journal_file):
    journal.upsert(
        {
            "client_request_id": "cr-sync",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "pending",
            "payload": {"total": 12.5, "items": [{"unit_price": 10}]},
        }
    )
    saved = journal.upsert(
        {
            "client_request_id": "cr-sync",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "synced",
            "server_sale_id": "sale-1",
            "server_reference": "POS-1",
            "payload": {"total": 1, "items": [{"unit_price": 1}]},
        }
    )
    assert saved["state"] == "synced"
    assert saved["server_sale_id"] == "sale-1"
    assert saved["payload"]["total"] == 12.5
    stale = journal.upsert(
        {
            "client_request_id": "cr-sync",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "pending",
            "payload": {"total": 4},
        }
    )
    assert stale["state"] == "synced"
    assert stale["server_sale_id"] == "sale-1"
    assert stale["payload"]["total"] == 12.5


def test_another_company_cannot_replace_the_sale(journal_file):
    journal.upsert(
        {
            "client_request_id": "cr-own",
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "pending",
            "payload": {"total": 8},
        }
    )
    with pytest.raises(journal.JournalError) as raised:
        journal.upsert(
            {
                "client_request_id": "cr-own",
                "tenant_id": "t2",
                "user_id": "u2",
                "state": "pending",
                "payload": {"total": 1},
            }
        )
    assert raised.value.status == 409
    row = journal.list_for("t1", "u1")[0]
    assert row["payload"]["total"] == 8
    assert journal.list_for("t2", "u2") == []


def test_journal_refuses_a_public_bind():
    with pytest.raises(SystemExit):
        journal.serve_forever(host="0.0.0.0", port=9)
