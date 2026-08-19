"""Stage 207 B1 — TLS ingress blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tls-ingress-blockers.json"


def test_tls_ingress_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 207 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_tls_ingress_claimed"] is False
    assert data["letsencrypt_issued"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_tls_ingress_acme_execution"] == "REMAINING"
    assert blockers["cert_manager_dns_http_provision"] == "REMAINING"
    assert blockers["stage29_t1_as_live_tls_ingress"] == "NON_CLAIM"
    assert blockers["live_tls_ingress_claimed"] == "false"
    assert blockers["letsencrypt_issued"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "tb-tls-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_tls_ingress_blockers_doc_b1():
    doc = (ROOT / "docs/TLS_INGRESS_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_tls_ingress_claimed" in doc
    assert "Stage 29" in doc
    assert "letsencrypt_issued" in doc
