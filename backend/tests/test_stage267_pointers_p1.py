"""Stage 267 P1 — Tenant company console pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tenant-company-console-pack-rg-pointers.json"


def test_tenant_company_console_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 267 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "tenant_company_console_stage68_t1",
        "ribdigi_house_console_pack_remaining_gate_stage266",
        "post_launch_continuity_pack_remaining_gate_stage265",
        "billing_deferred_honesty_stage36",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tccprp-tenant-erp-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tenant_company_console_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/TENANT_COMPANY_CONSOLE_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "TENANT_COMPANY_CONSOLE_MVP.md" in doc
    assert "RIBDIGI_HOUSE_CONSOLE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "POST_LAUNCH_CONTINUITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "BILLING_DEFERRED_HONESTY_MVP.md" in doc
    assert "billing_complete_claimed" in doc
    assert "tenant_modules_reclaimed_complete" in doc
