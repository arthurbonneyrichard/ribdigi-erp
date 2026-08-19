"""Stage 258 B1 — steady-state ops pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "steady-state-ops-pack-rg-blockers.json"


def test_steady_state_ops_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 258 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["steady_state_ops_claimed"] is False
    assert data["first_commercial_day_claimed"] is False
    blockers = data["blockers"]
    assert blockers["steady_state_ops_complete"] == "REMAINING"
    assert blockers["commercial_acceptance_complete"] == "REMAINING"
    assert blockers["first_commercial_day_complete"] == "REMAINING"
    assert blockers["stage71_s1_as_steady_state_live"] == "NON_CLAIM"
    assert blockers["steady_state_ops_claimed"] == "false"
    assert blockers["first_commercial_day_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ssoprb-steady-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_steady_state_ops_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/STEADY_STATE_OPS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "steady_state_ops_claimed" in doc
    assert "first_commercial_day_claimed" in doc
    assert "Stage 71" in doc
