"""Stage 224 P1 — load capacity RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "load-capacity-rg-pointers.json"


def test_load_capacity_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 224 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["live_load_capacity_claimed"] is False
    assert data["operator_1000vu_executed"] is False
    for topic in (
        "load_capacity_stage26_c1",
        "load_cert_pack_remaining_gate_stage223",
        "grafana_pack_remaining_gate_stage222",
        "load_cert_pack_stage28_c1",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcpp-live-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_load_capacity_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LOAD_CAPACITY_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LOAD_CAPACITY_MVP.md" in doc
    assert "LOAD_CERT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "GRAFANA_PACK_REMAINING_GATE_MVP.md" in doc
    assert "live_load_capacity_claimed" in doc
