"""Stage 226 P1 — PgBouncer live RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-live-rg-pointers.json"


def test_pgbouncer_live_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 226 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_pgbouncer_claimed"] is False
    assert data["helm_pooler_default_claimed"] is False
    for topic in (
        "pgbouncer_mvp_stage27_p1",
        "pgbouncer_soak_pack_stage29_b2",
        "pgbouncer_soak_remaining_gate_stage208",
        "loadtest_baseline_remaining_gate_stage225",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pblp-live-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_live_rg_pointers_doc_p1():
    doc = (ROOT / "docs/PGBOUNCER_LIVE_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PGBOUNCER_MVP.md" in doc
    assert "PGBOUNCER_SOAK_REMAINING_GATE_MVP.md" in doc
    assert "LOADTEST_BASELINE_REMAINING_GATE_MVP.md" in doc
    assert "live_pgbouncer_claimed" in doc
