"""Stage 227 P1 — cutover pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cutover-pack-rg-pointers.json"


def test_cutover_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 227 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["production_cutover_claimed"] is False
    assert data["section_7_signed"] is False
    for topic in (
        "cutover_pack_stage29_x1",
        "cutover_remaining_gate_stage203",
        "pgbouncer_live_remaining_gate_stage226",
        "launch_cert_stage27_l1",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cprp-cutover-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cutover_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/CUTOVER_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CUTOVER_PACK_MVP.md" in doc
    assert "CUTOVER_REMAINING_GATE_MVP.md" in doc
    assert "PGBOUNCER_LIVE_REMAINING_GATE_MVP.md" in doc
    assert "production_cutover_claimed" in doc
