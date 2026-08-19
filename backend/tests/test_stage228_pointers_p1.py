"""Stage 228 P1 — TLS ingress pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tls-ingress-pack-rg-pointers.json"


def test_tls_ingress_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 228 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["tls_cutover_claimed"] is False
    assert data["letsencrypt_issued"] is False
    for topic in (
        "tls_ingress_pack_stage29_t1",
        "tls_ingress_remaining_gate_stage207",
        "cutover_pack_remaining_gate_stage227",
        "k8s_deploy_stage26_k1",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tiprp-tls-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tls_ingress_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/TLS_INGRESS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "TLS_INGRESS_PACK_MVP.md" in doc
    assert "TLS_INGRESS_REMAINING_GATE_MVP.md" in doc
    assert "CUTOVER_PACK_REMAINING_GATE_MVP.md" in doc
    assert "tls_cutover_claimed" in doc
