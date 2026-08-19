"""Stage 205 B1 — staging GHA blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "staging-gha-blockers.json"


def test_staging_gha_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 205 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_staging_apply_claimed"] is False
    assert data["gha_staging_wired_into_main_ci"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_staging_gha_apply_execution"] == "REMAINING"
    assert blockers["staging_secrets_cluster_provision"] == "REMAINING"
    assert blockers["stage28_g1_as_live_staging_apply"] == "NON_CLAIM"
    assert blockers["main_ci_staging_deploy_wiring"] == "NON_CLAIM"
    assert blockers["live_staging_apply_claimed"] == "false"
    assert blockers["gha_staging_wired_into_main_ci"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "sb-apply-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_staging_gha_blockers_doc_b1():
    doc = (ROOT / "docs/STAGING_GHA_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_staging_apply_claimed" in doc
    assert "Stage 28" in doc
    assert "ci.yml" in doc or "main" in doc.lower()
