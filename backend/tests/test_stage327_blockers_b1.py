"""Stage 327 B1 — ops monitoring pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ops-monitoring-pack-rg-blockers.json"


def test_ops_monitoring_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 327 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_ops_monitoring_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_ops_monitoring_claimed"] == "REMAINING"
    assert blockers["live_monitoring_claimed"] == "REMAINING"
    assert blockers["hosted_grafana_claimed"] == "REMAINING"
    assert blockers["paging_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["stage221_as_live_ops_monitoring"] == "NON_CLAIM"
    assert blockers["live_ops_monitoring_claimed_flag"] == "false"
    assert blockers["hosted_grafana_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "omprb-monitoring-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ops_monitoring_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/OPS_MONITORING_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_ops_monitoring_claimed" in doc
    assert "hosted_grafana_claimed" in doc
    assert "Stage 221" in doc
