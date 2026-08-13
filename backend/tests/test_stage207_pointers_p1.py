"""Stage 207 P1 — TLS ingress pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tls-ingress-pack-pointers.json"


def test_tls_ingress_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 207 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_tls_ingress_claimed"] is False
    assert data["letsencrypt_issued"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "tls_ingress_pack_stage29",
        "cluster_issuer_examples",
        "ingress_tls_examples",
        "k8s_deploy_remaining_gate_stage206",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tp-tls-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tls_ingress_pack_pointers_doc_p1():
    doc = (ROOT / "docs/TLS_INGRESS_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "TLS_INGRESS_PACK_MVP.md" in doc
    assert "K8S_DEPLOY_REMAINING_GATE_MVP.md" in doc
    assert "cluster-issuer" in doc or "ClusterIssuer" in doc
    assert "live_tls_ingress_claimed" in doc
