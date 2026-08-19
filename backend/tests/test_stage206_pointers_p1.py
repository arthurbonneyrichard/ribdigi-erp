"""Stage 206 P1 — k8s deploy pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "k8s-deploy-pack-pointers.json"


def test_k8s_deploy_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 206 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_cluster_deploy_claimed"] is False
    assert data["ci_deploy_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "k8s_deploy_stage26",
        "helm_install_helper",
        "staging_smoke_helper",
        "staging_gha_remaining_gate_stage205",
        "deploy_free_ci_stage18",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kp-deploy-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_k8s_deploy_pack_pointers_doc_p1():
    doc = (ROOT / "docs/K8S_DEPLOY_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "K8S_DEPLOY_MVP.md" in doc
    assert "STAGING_GHA_REMAINING_GATE_MVP.md" in doc
    assert "ci.yml" in doc
    assert "live_cluster_deploy_claimed" in doc
