"""Stage 318 B1 — k8s deploy pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "k8s-deploy-pack-rg-blockers.json"


def test_k8s_deploy_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 318 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_cluster_deploy_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_cluster_deploy_claimed"] == "REMAINING"
    assert blockers["ci_deploy_claimed"] == "REMAINING"
    assert blockers["live_staging_apply_claimed"] == "REMAINING"
    assert blockers["managed_data_plane_claimed"] == "REMAINING"
    assert blockers["stage26_as_live_cluster_deploy"] == "NON_CLAIM"
    assert blockers["live_cluster_deploy_claimed_flag"] == "false"
    assert blockers["ci_deploy_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kdprb-deploy-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_k8s_deploy_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/K8S_DEPLOY_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_cluster_deploy_claimed" in doc
    assert "ci_deploy_claimed" in doc
    assert "Stage 26" in doc
