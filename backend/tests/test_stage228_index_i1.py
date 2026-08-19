"""Stage 228 I1 — TLS ingress pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tls-ingress-pack-remaining-gate.json"


def test_tls_ingress_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 228 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["tls_cutover_claimed"] is False
    assert data["letsencrypt_issued"] is False
    assert data["live_tls_ingress_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage29_t1_tls_ingress_pack"] is True
    assert data["distinct_from_stage207_tls_ingress_remaining_gate"] is True
    assert data["distinct_from_stage227_cutover_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tipr-tls-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tls_ingress_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/TLS_INGRESS_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "tls_cutover_claimed" in doc
    assert "TLS_INGRESS_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "TLS_INGRESS_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 29" in doc
    assert "Stage 207" in doc
