"""Stage 269 B1 — Platform principal pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "platform-principal-pack-rg-blockers.json"


def test_platform_principal_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 269 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["platform_ops_live_complete"] == "REMAINING"
    assert blockers["cross_principal_leak_complete"] == "REMAINING"
    assert blockers["adr137_as_platform_ops_complete"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed"] == "false"
    assert blockers["platform_ops_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ppprb-platform-ops-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_platform_principal_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PLATFORM_PRINCIPAL_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "platform_ops_live_claimed" in doc
    assert "ADR-137" in doc or "ADR_137" in doc
