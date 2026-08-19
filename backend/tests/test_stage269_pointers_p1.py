"""Stage 269 P1 — Platform principal pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "platform-principal-pack-rg-pointers.json"


def test_platform_principal_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 269 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "platform_principal_adr137",
        "dual_console_pack_remaining_gate_stage268",
        "tenant_company_console_pack_remaining_gate_stage267",
        "ribdigi_house_console_pack_remaining_gate_stage266",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ppprp-platform-ops-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_platform_principal_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PLATFORM_PRINCIPAL_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_137_PLATFORM_PRINCIPAL.md" in doc
    assert "DUAL_CONSOLE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "TENANT_COMPANY_CONSOLE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "RIBDIGI_HOUSE_CONSOLE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "billing_complete_claimed" in doc
    assert "platform_ops_live_claimed" in doc
