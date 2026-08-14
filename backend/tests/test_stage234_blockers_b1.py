"""Stage 234 B1 — load capacity pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "load-capacity-pack-rg-blockers.json"


def test_load_capacity_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 234 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["certified_1000vu_claimed"] is False
    assert data["live_load_capacity_claimed"] is False
    assert data["operator_1000vu_executed"] is False
    assert data["ci_1000vu_certificate_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["operator_staging_1000vu_execution"] == "REMAINING"
    assert blockers["ci_1000vu_certificate"] == "REMAINING"
    assert blockers["live_sized_infra_capacity"] == "REMAINING"
    assert blockers["stage26_c1_as_live_capacity"] == "NON_CLAIM"
    assert blockers["stage28_c1_as_certified_1000vu"] == "NON_CLAIM"
    assert blockers["certified_1000vu_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcprb-cert-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_load_capacity_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/LOAD_CAPACITY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "certified_1000vu_claimed" in doc
    assert "Stage 26" in doc
    assert "Stage 28" in doc
