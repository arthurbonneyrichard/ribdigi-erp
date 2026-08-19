"""Stage 327 P1 — ops monitoring pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ops-monitoring-pack-rg-pointers.json"


def test_ops_monitoring_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 327 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_ops_monitoring_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "ops_monitoring_remaining_gate_stage221",
        "hosted_faq_saas_pack_remaining_gate_stage326",
        "golive_pack_remaining_gate_stage325",
        "ops_monitoring_stage26",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "omprp-monitoring-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ops_monitoring_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/OPS_MONITORING_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "OPS_MONITORING_REMAINING_GATE_MVP.md" in doc
    assert "HOSTED_FAQ_SAAS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "GOLIVE_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OPS_MONITORING_MVP.md" in doc
    assert "live_ops_monitoring_claimed" in doc
    assert "hosted_grafana_claimed" in doc
