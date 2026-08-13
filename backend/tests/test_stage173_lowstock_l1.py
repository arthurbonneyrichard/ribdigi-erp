"""Stage 173 L1 — store select + low-stock glance packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "store-open-lowstock.json"


def test_store_open_lowstock_register_l1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 173 and data["pack"] == "L1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["attestation_claimed"] is False
    assert data["offline_stock_authoritative"] is False
    assert data["auto_po_claimed"] is False
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ls-offline-complete-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_store_open_lowstock_doc_l1():
    doc = (ROOT / "docs/STORE_OPEN_LOWSTOCK_MVP.md").read_text(encoding="utf-8")
    assert "Low stock" in doc or "low-stock" in doc.lower()
    assert "store" in doc.lower()
    assert "non-authoritative" in doc or "authoritative" in doc
    assert "offline_complete_claimed" in doc
