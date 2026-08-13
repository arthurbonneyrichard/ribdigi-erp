"""Stage 209 P1 — pentest pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pentest-pack-pointers.json"


def test_pentest_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 209 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["vendor_pen_test_purchased"] is False
    assert data["live_zap_executed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "pentest_pack_stage29",
        "engagement_checklist",
        "vendor_engagement_schema",
        "security_scan_stage27",
        "pgbouncer_soak_remaining_gate_stage208",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pp-pentest-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_pentest_pack_pointers_doc_p1():
    doc = (ROOT / "docs/PENTEST_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "PENTEST_PACK_MVP.md" in doc
    assert "PGBOUNCER_SOAK_REMAINING_GATE_MVP.md" in doc
    assert "pentest-engagement-checklist" in doc
    assert "vendor_pen_test_purchased" in doc
