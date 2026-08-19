"""Stage 221 B1 — ops monitoring blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ops-monitoring-blockers.json"


def test_ops_monitoring_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 221 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_ops_monitoring_claimed"] is False
    assert data["live_monitoring_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["hosted_prometheus_grafana_stack"] == "REMAINING"
    assert blockers["alertmanager_pagerduty_routing"] == "REMAINING"
    assert blockers["stage26_m1_as_live_monitoring"] == "NON_CLAIM"
    assert blockers["live_monitoring_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "omb-monitoring-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ops_monitoring_blockers_doc_b1():
    doc = (ROOT / "docs/OPS_MONITORING_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_monitoring_claimed" in doc
    assert "Stage 26" in doc
