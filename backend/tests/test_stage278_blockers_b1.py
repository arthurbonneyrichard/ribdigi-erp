"""Stage 278 B1 — Data portability pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-portability-pack-rg-blockers.json"


def test_data_portability_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 278 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["gdpr_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["gdpr_complete"] == "REMAINING"
    assert blockers["dsar_portal_complete"] == "REMAINING"
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["stage37_as_gdpr_complete"] == "NON_CLAIM"
    assert blockers["gdpr_complete_claimed"] == "false"
    assert blockers["dsar_portal_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "dpprb-gdpr-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_data_portability_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/DATA_PORTABILITY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "gdpr_complete_claimed" in doc
    assert "dsar_portal_claimed" in doc
    assert "Stage 37" in doc
