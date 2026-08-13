"""Stage 222 I1 — Grafana pack remaining-gate index hub packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "grafana-pack-remaining-gate.json"


def test_grafana_pack_remaining_gate_register_i1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 222 and data["pack"] == "I1"
    assert data["packaging_complete"] is True
    assert data["live_grafana_pack_claimed"] is False
    assert data["hosted_grafana_claimed"] is False
    assert data["pagerduty_wired"] is False
    assert data["go_live_claimed"] is False
    assert data["distinct_from_stage28_a1_grafana_pack"] is True
    assert data["distinct_from_stage221_ops_monitoring_remaining_gate"] is True
    assert data["distinct_from_stage220_support_sla_boundary_remaining_gate"] is True
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "gp-grafana-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_grafana_pack_remaining_gate_doc_i1():
    doc = (ROOT / "docs/GRAFANA_PACK_REMAINING_GATE_MVP.md").read_text(encoding="utf-8")
    assert "live_grafana_pack_claimed" in doc
    assert "GRAFANA_PACK_BLOCKERS_MVP.md" in doc
    assert "GRAFANA_PACK_RG_POINTERS_MVP.md" in doc
    assert "Stage 28" in doc
