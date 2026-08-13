"""Stage 221 P1 — ops monitoring RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ops-monitoring-rg-pointers.json"


def test_ops_monitoring_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 221 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_ops_monitoring_claimed"] is False
    assert data["live_monitoring_claimed"] is False
    for topic in (
        "ops_monitoring_stage26_m1",
        "grafana_pack_stage28_a1",
        "support_sla_boundary_remaining_gate_stage220",
        "production_hypercare_remaining_gate_stage219",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "omp-monitoring-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ops_monitoring_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OPS_MONITORING_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "OPS_MONITORING_MVP.md" in doc
    assert "SUPPORT_SLA_BOUNDARY_REMAINING_GATE_MVP.md" in doc
    assert "PRODUCTION_HYPERCARE_REMAINING_GATE_MVP.md" in doc
    assert "live_ops_monitoring_claimed" in doc
