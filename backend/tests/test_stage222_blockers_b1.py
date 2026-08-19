"""Stage 222 B1 — Grafana pack blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "grafana-pack-blockers.json"


def test_grafana_pack_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 222 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_grafana_pack_claimed"] is False
    assert data["hosted_grafana_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["hosted_grafana_dashboards_deployed"] == "REMAINING"
    assert blockers["alertmanager_pagerduty_wired"] == "REMAINING"
    assert blockers["stage28_a1_as_hosted_grafana"] == "NON_CLAIM"
    assert blockers["hosted_grafana_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "gpb-grafana-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_grafana_pack_blockers_doc_b1():
    doc = (ROOT / "docs/GRAFANA_PACK_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "hosted_grafana_claimed" in doc
    assert "Stage 28" in doc
