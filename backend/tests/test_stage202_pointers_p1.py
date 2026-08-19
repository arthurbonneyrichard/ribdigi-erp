"""Stage 202 P1 — production launch pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "production-launch-pack-pointers.json"


def test_production_launch_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 202 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["production_launch_live_claimed"] is False
    assert data["production_cutover_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "production_launch_stage66",
        "cutover_pack_stage29",
        "preflight_verification_remaining_gate_stage201",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "pp-launch-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_production_launch_pack_pointers_doc_p1():
    doc = (ROOT / "docs/PRODUCTION_LAUNCH_PACK_POINTERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "PRODUCTION_LAUNCH_MVP.md" in doc
    assert "CUTOVER_PACK_MVP.md" in doc
    assert "PREFLIGHT_VERIFICATION_REMAINING_GATE_MVP.md" in doc
    assert "production_launch_live_claimed" in doc
