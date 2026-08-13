"""Stage 208 B1 — PgBouncer soak blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-soak-blockers.json"


def test_pgbouncer_soak_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 208 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_soak_executed"] is False
    assert data["helm_pooler_default_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_pgbouncer_soak_execution"] == "REMAINING"
    assert blockers["pooler_deploy_database_url_show_pools"] == "REMAINING"
    assert blockers["stage29_b2_as_live_soak"] == "NON_CLAIM"
    assert blockers["live_soak_executed"] == "false"
    assert blockers["helm_pooler_default_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pb-soak-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_soak_blockers_doc_b1():
    doc = (ROOT / "docs/PGBOUNCER_SOAK_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_soak_executed" in doc
    assert "Stage 29" in doc
    assert "helm_pooler_default_claimed" in doc
