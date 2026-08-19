"""Stage 226 B1 — PgBouncer live blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-live-blockers.json"


def test_pgbouncer_live_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 226 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_pgbouncer_claimed"] is False
    assert data["helm_pooler_default_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_pgbouncer_data_plane"] == "REMAINING"
    assert blockers["default_helm_pooler"] == "REMAINING"
    assert blockers["stage27_p1_stage29_b2_as_live_pgbouncer"] == "NON_CLAIM"
    assert blockers["live_pgbouncer_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pblb-live-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_live_blockers_doc_b1():
    doc = (ROOT / "docs/PGBOUNCER_LIVE_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_pgbouncer_claimed" in doc
    assert "Stage 27" in doc
