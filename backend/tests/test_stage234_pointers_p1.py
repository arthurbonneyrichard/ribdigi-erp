"""Stage 234 P1 — load capacity pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "load-capacity-pack-rg-pointers.json"


def test_load_capacity_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 234 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["certified_1000vu_claimed"] is False
    assert data["live_load_capacity_claimed"] is False
    for topic in (
        "load_capacity_stage26_c1",
        "load_cert_pack_stage28_c1",
        "load_capacity_remaining_gate_stage224",
        "load_cert_pack_remaining_gate_stage223",
        "wal_offsite_remaining_gate_stage233",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "lcprp-cert-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_load_capacity_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/LOAD_CAPACITY_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "LOAD_CAPACITY_MVP.md" in doc
    assert "LOAD_CERT_PACK_MVP.md" in doc
    assert "LOAD_CAPACITY_REMAINING_GATE_MVP.md" in doc
    assert "LOAD_CERT_PACK_REMAINING_GATE_MVP.md" in doc
    assert "certified_1000vu_claimed" in doc
