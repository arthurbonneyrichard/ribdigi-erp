"""Stage 318 P1 — k8s deploy pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "k8s-deploy-pack-rg-pointers.json"


def test_k8s_deploy_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 318 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_cluster_deploy_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "k8s_deploy_stage26",
        "pgbouncer_soak_pack_remaining_gate_stage317",
        "pentest_pack_remaining_gate_stage316",
        "k8s_deploy_remaining_gate_stage206",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "kdprp-deploy-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_k8s_deploy_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/K8S_DEPLOY_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "K8S_DEPLOY_MVP.md" in doc
    assert "PGBOUNCER_SOAK_PACK_REMAINING_GATE_MVP.md" in doc
    assert "PENTEST_PACK_REMAINING_GATE_MVP.md" in doc
    assert "K8S_DEPLOY_REMAINING_GATE_MVP.md" in doc
    assert "live_cluster_deploy_claimed" in doc
    assert "ci_deploy_claimed" in doc
