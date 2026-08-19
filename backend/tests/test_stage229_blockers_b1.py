"""Stage 229 B1 — staging GHA pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "staging-gha-pack-rg-blockers.json"


def test_staging_gha_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 229 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_staging_apply_claimed"] is False
    assert data["gha_staging_wired_into_main_ci"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_gha_staging_apply"] == "REMAINING"
    assert blockers["staging_deploy_in_main_ci"] == "REMAINING"
    assert blockers["stage28_g1_as_live_staging_apply"] == "NON_CLAIM"
    assert blockers["live_staging_apply_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sgprb-apply-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_staging_gha_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/STAGING_GHA_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_staging_apply_claimed" in doc
    assert "Stage 28" in doc
