"""Stage 172 B1 — bind + catalog day-one packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-bind-catalog.json"


def test_cashier_bind_catalog_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 172 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["catalog_ttl_hours"] == 4
    assert data["stock_authoritative_offline"] is False
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "bc-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_bind_catalog_doc_b1():
    doc = (ROOT / "docs/CASHIER_BIND_CATALOG_MVP.md").read_text(encoding="utf-8")
    assert "Bind browser" in doc or "bind" in doc.lower()
    assert "4 hour" in doc or "4 hours" in doc or "TTL" in doc
    assert "non-authoritative" in doc
    assert "offline_complete_claimed" in doc
