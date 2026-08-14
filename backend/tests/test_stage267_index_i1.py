"""Stage 267 I1 — Tenant company console pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tenant-company-console-pack-remaining-gate.json"


def test_tenant_company_console_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 267 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["tenant_modules_reclaimed_complete"] is False
    assert data["demo_tenant_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage68_t1_tenant_company_console"] is True
    assert data["distinct_from_stage266_ribdigi_house_console_pack_remaining_gate"] is True
    assert data["distinct_from_stage265_post_launch_continuity_pack_remaining_gate"] is True
    assert data["distinct_from_stage239_operator_handoff_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tccpr-tenant-erp-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tenant_company_console_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/TENANT_COMPANY_CONSOLE_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "tenant_modules_reclaimed_complete" in doc
    assert "TENANT_COMPANY_CONSOLE_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "TENANT_COMPANY_CONSOLE_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 68" in doc
    assert "Stage 36" in doc or "billing" in doc.lower()
