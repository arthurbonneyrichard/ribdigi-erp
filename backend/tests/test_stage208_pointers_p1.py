"""Stage 208 P1 — PgBouncer soak pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pgbouncer-soak-pack-pointers.json"


def test_pgbouncer_soak_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 208 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_soak_executed"] is False
    assert data["helm_pooler_default_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "pgbouncer_soak_pack_stage29",
        "soak_checklist",
        "soak_evidence_schema",
        "tls_ingress_remaining_gate_stage207",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pp-soak-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pgbouncer_soak_pack_pointers_doc_p1():
    doc = (ROOT / "docs/PGBOUNCER_SOAK_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PGBOUNCER_SOAK_PACK_MVP.md" in doc
    assert "TLS_INGRESS_REMAINING_GATE_MVP.md" in doc
    assert "pgbouncer-soak-checklist" in doc
    assert "live_soak_executed" in doc
