"""Stage 236 B1 — support runbook pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-runbook-pack-rg-blockers.json"


def test_support_runbook_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 236 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_support_sla_claimed"] is False
    assert data["live_support_runbook_claimed"] is False
    assert data["hosted_support_desk_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_support_sla_oncall_rota"] == "REMAINING"
    assert blockers["hosted_support_desk"] == "REMAINING"
    assert blockers["stage30_s1_as_live_support_sla"] == "NON_CLAIM"
    assert blockers["live_support_sla_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "srprb-sla-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_support_runbook_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/SUPPORT_RUNBOOK_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_support_sla_claimed" in doc
    assert "Stage 30" in doc
