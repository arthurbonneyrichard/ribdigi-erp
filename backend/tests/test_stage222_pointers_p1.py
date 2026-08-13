"""Stage 222 P1 — Grafana pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "grafana-pack-rg-pointers.json"


def test_grafana_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 222 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_grafana_pack_claimed"] is False
    assert data["hosted_grafana_claimed"] is False
    for topic in (
        "grafana_pack_stage28_a1",
        "alertmanager_example_stage28_a1",
        "ops_monitoring_remaining_gate_stage221",
        "support_sla_boundary_remaining_gate_stage220",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "gpp-grafana-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_grafana_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/GRAFANA_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "GRAFANA_PACK_MVP.md" in doc
    assert "OPS_MONITORING_REMAINING_GATE_MVP.md" in doc
    assert "SUPPORT_SLA_BOUNDARY_REMAINING_GATE_MVP.md" in doc
    assert "live_grafana_pack_claimed" in doc
