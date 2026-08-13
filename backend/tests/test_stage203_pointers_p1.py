"""Stage 203 P1 — cutover pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cutover-pack-pointers.json"


def test_cutover_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 203 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["production_cutover_claimed"] is False
    assert data["section_7_signed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "cutover_pack_stage29",
        "launch_cert_stage27",
        "production_launch_remaining_gate_stage202",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cp-cutover-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_cutover_pack_pointers_doc_p1():
    doc = (ROOT / "docs/CUTOVER_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "CUTOVER_PACK_MVP.md" in doc
    assert "LAUNCH_CERT_MVP.md" in doc
    assert "PRODUCTION_LAUNCH_REMAINING_GATE_MVP.md" in doc
    assert "production_cutover_claimed" in doc
