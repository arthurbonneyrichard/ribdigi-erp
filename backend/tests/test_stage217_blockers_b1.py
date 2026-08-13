"""Stage 217 B1 — operator handoff blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "operator-handoff-blockers.json"


def test_operator_handoff_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 217 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_operator_handoff_claimed"] is False
    assert data["handoff_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_ops_takeover_handoff"] == "REMAINING"
    assert blockers["section_7_name_date_verification"] == "REMAINING"
    assert blockers["stage32_h1_as_live_handoff"] == "NON_CLAIM"
    assert blockers["handoff_complete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ohb-handoff-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_operator_handoff_blockers_doc_b1():
    doc = (ROOT / "docs/OPERATOR_HANDOFF_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "handoff_complete_claimed" in doc
    assert "Stage 32" in doc
