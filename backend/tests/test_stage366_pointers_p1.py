"""Stage 366 P1 — AR/AP accounting surface pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ar-ap-accounting-surface-pack-rg-pointers.json"


def test_ar_ap_accounting_surface_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 366 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["new_ar_ap_engine_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "ar_ap_accounting_surface_stage232",
        "e2e_verify_financials_pack_remaining_gate_stage365",
        "e2e_backup_restore_pack_remaining_gate_stage320",
        "offline_complete_pack_remaining_gate_stage329",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "aaasprp-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ar_ap_accounting_surface_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/AR_AP_ACCOUNTING_SURFACE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "AR_AP_ACCOUNTING_SURFACE_MVP.md" in doc
    assert "E2E_VERIFY_FINANCIALS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "E2E_BACKUP_RESTORE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OFFLINE_COMPLETE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "new_ar_ap_engine_claimed" in doc
    assert "open_banking_claimed" in doc
