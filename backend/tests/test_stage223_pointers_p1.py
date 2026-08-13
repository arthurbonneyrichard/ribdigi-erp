"""Stage 223 P1 — load cert pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "load-cert-pack-rg-pointers.json"


def test_load_cert_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 223 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_load_cert_pack_claimed"] is False
    assert data["operator_1000vu_executed"] is False
    for topic in (
        "load_cert_pack_stage28_c1",
        "load_capacity_stage26_c1",
        "grafana_pack_remaining_gate_stage222",
        "ops_monitoring_remaining_gate_stage221",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcp-1000vu-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_load_cert_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LOAD_CERT_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LOAD_CERT_PACK_MVP.md" in doc
    assert "GRAFANA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "OPS_MONITORING_REMAINING_GATE_MVP.md" in doc
    assert "live_load_cert_pack_claimed" in doc
