"""Stage 204 P1 — launch cert pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "launch-cert-pack-pointers.json"


def test_launch_cert_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 204 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["production_signoff_claimed"] is False
    assert data["section_7_signed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "launch_cert_stage27",
        "staging_gha_stage28",
        "cutover_remaining_gate_stage203",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lp-cert-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_launch_cert_pack_pointers_doc_p1():
    doc = (ROOT / "docs/LAUNCH_CERT_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LAUNCH_CERT_MVP.md" in doc
    assert "STAGING_GHA_MVP.md" in doc
    assert "CUTOVER_REMAINING_GATE_MVP.md" in doc
    assert "production_signoff_claimed" in doc
