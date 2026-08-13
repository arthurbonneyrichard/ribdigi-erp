"""Stage 206 B1 — k8s deploy blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "k8s-deploy-blockers.json"


def test_k8s_deploy_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 206 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_cluster_deploy_claimed"] is False
    assert data["ci_deploy_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_cluster_deploy_execution"] == "REMAINING"
    assert blockers["cluster_secrets_data_plane_provision"] == "REMAINING"
    assert blockers["stage26_k1_as_live_cluster_deploy"] == "NON_CLAIM"
    assert blockers["main_ci_deploy_wiring"] == "NON_CLAIM"
    assert blockers["live_cluster_deploy_claimed"] == "false"
    assert blockers["ci_deploy_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kb-deploy-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_k8s_deploy_blockers_doc_b1():
    doc = (ROOT / "docs/K8S_DEPLOY_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_cluster_deploy_claimed" in doc
    assert "Stage 26" in doc
    assert "ci.yml" in doc or "main" in doc.lower()
