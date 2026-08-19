"""Stage 317 I1 — PgBouncer soak pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-soak-pack-remaining-gate.json"


def test_pgbouncer_soak_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 317 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_soak_executed"] is False
    assert data["helm_pooler_default_claimed"] is False
    assert data["managed_cloud_pooler_claimed"] is False
    assert data["live_tls_ingress_claimed"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage29_pgbouncer_soak_pack"] is True
    assert data["distinct_from_stage208_pgbouncer_soak_remaining_gate"] is True
    assert data["distinct_from_stage316_pentest_pack_remaining_gate"] is True
    assert data["distinct_from_stage315_security_scan_pack_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pspr-soak-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_soak_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/PGBOUNCER_SOAK_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_soak_executed" in doc
    assert "helm_pooler_default_claimed" in doc
    assert "PGBOUNCER_SOAK_PACK_RG_BLOCKERS_MVP.md" in doc
    assert "PGBOUNCER_SOAK_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 29" in doc
    assert "PGBOUNCER_SOAK_PACK_MVP.md" in doc
    assert "PGBOUNCER_SOAK_REMAINING_GATE_MVP.md" in doc
