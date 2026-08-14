"""Stage 243 B1 — professional services SOW pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "professional-services-sow-pack-rg-blockers.json"


def test_professional_services_sow_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 243 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["signed_sow_claimed"] is False
    assert data["implementation_delivery_claimed"] is False
    assert data["professional_services_live_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["signed_sow_execution"] == "REMAINING"
    assert blockers["implementation_delivery_complete"] == "REMAINING"
    assert blockers["stage48_p1_as_signed_sow"] == "NON_CLAIM"
    assert blockers["stage48_p1_as_implementation_delivery"] == "NON_CLAIM"
    assert blockers["stage242_i1_as_signed_sow"] == "NON_CLAIM"
    assert blockers["signed_sow_claimed"] == "false"
    assert blockers["implementation_delivery_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pssprb-sow-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_professional_services_sow_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PROFESSIONAL_SERVICES_SOW_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "signed_sow_claimed" in doc
    assert "implementation_delivery_claimed" in doc
    assert "Stage 48" in doc
