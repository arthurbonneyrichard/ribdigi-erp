"""Stage 296 B1 — Commercial status pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-status-pack-rg-blockers.json"


def test_commercial_status_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 296 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["status_page_live"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["status_page_live"] == "REMAINING"
    assert blockers["uptime_sla_claimed"] == "REMAINING"
    assert blockers["measured_uptime_claimed"] == "REMAINING"
    assert blockers["commercial_support_claimed"] == "REMAINING"
    assert blockers["stage74_as_status_page_live"] == "NON_CLAIM"
    assert blockers["status_page_live_claimed"] == "false"
    assert blockers["uptime_sla_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cstprb-status-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_status_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_STATUS_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "status_page_live" in doc
    assert "uptime_sla_claimed" in doc
    assert "Stage 74" in doc
