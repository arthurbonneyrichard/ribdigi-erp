"""Stage 357 P1 — cashier bind catalog pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cashier-bind-catalog-pack-rg-pointers.json"


def test_cashier_bind_catalog_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 357 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["offline_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "cashier_bind_catalog_stage172",
        "store_open_lowstock_pack_remaining_gate_stage356",
        "cashier_quickstart_pack_remaining_gate_stage339",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cbcprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cashier_bind_catalog_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/CASHIER_BIND_CATALOG_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CASHIER_BIND_CATALOG_MVP.md" in doc
    assert "STORE_OPEN_LOWSTOCK_PACK_REMAINING_GATE_MVP.md" in doc
    assert "CASHIER_QUICKSTART_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "offline_complete_claimed" in doc
    assert "usb_serial_claimed" in doc
