"""Stage 317 B1 — PgBouncer soak pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-soak-pack-rg-blockers.json"


def test_pgbouncer_soak_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 317 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_soak_executed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_soak_executed"] == "REMAINING"
    assert blockers["helm_pooler_default_claimed"] == "REMAINING"
    assert blockers["managed_cloud_pooler_claimed"] == "REMAINING"
    assert blockers["live_tls_ingress_claimed"] == "REMAINING"
    assert blockers["stage29_as_live_soak"] == "NON_CLAIM"
    assert blockers["live_soak_executed_flag"] == "false"
    assert blockers["helm_pooler_default_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "psprb-soak-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_soak_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/PGBOUNCER_SOAK_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_soak_executed" in doc
    assert "helm_pooler_default_claimed" in doc
    assert "Stage 29" in doc
