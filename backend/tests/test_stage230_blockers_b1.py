"""Stage 230 B1 — launch cert pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "launch-cert-pack-rg-blockers.json"


def test_launch_cert_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 230 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["production_signoff_claimed"] is False
    assert data["section_7_signed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["production_launch_signoff"] == "REMAINING"
    assert blockers["launch_section_7_signoff"] == "REMAINING"
    assert blockers["stage27_l1_as_production_signoff"] == "NON_CLAIM"
    assert blockers["production_signoff_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcprb-signoff-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_launch_cert_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LAUNCH_CERT_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "production_signoff_claimed" in doc
    assert "Stage 27" in doc
