"""Stage 228 B1 — TLS ingress pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tls-ingress-pack-rg-blockers.json"


def test_tls_ingress_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 228 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["tls_cutover_claimed"] is False
    assert data["letsencrypt_issued"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_tls_https_cutover"] == "REMAINING"
    assert blockers["letsencrypt_acme_issuance"] == "REMAINING"
    assert blockers["stage29_t1_as_live_tls_cutover"] == "NON_CLAIM"
    assert blockers["tls_cutover_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tiprb-tls-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tls_ingress_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/TLS_INGRESS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "tls_cutover_claimed" in doc
    assert "Stage 29" in doc
