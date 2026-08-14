"""Stage 269 I1 — Platform principal pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "platform-principal-pack-remaining-gate.json"


def test_platform_principal_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 269 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["platform_ops_live_claimed"] is False
    assert data["cross_principal_leak_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_adr137_platform_principal"] is True
    assert data["distinct_from_stage268_dual_console_pack_remaining_gate"] is True
    assert data["distinct_from_stage267_tenant_company_console_pack_remaining_gate"] is True
    assert data["distinct_from_stage266_ribdigi_house_console_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pppr-platform-ops-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_platform_principal_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PLATFORM_PRINCIPAL_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "platform_ops_live_claimed" in doc
    assert "PLATFORM_PRINCIPAL_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "PLATFORM_PRINCIPAL_PACK_RG_POINTERS_MVP.md" in doc
    assert "ADR-137" in doc or "ADR_137" in doc
    assert "Stage 268" in doc
