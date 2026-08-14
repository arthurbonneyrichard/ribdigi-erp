"""Stage 312 B1 — status uptime pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "status-uptime-pack-rg-blockers.json"


def test_status_uptime_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 312 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["status_page_live"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["status_page_live"] == "REMAINING"
    assert blockers["uptime_sla_claimed"] == "REMAINING"
    assert blockers["measured_uptime_claimed"] == "REMAINING"
    assert blockers["public_dashboard_claimed"] == "REMAINING"
    assert blockers["stage40_as_status_page"] == "NON_CLAIM"
    assert blockers["status_page_live_flag"] == "false"
    assert blockers["uptime_sla_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "suprb-page-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_status_uptime_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/STATUS_UPTIME_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "status_page_live" in doc
    assert "measured_uptime_claimed" in doc
    assert "Stage 40" in doc
