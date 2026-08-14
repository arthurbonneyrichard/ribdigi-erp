"""Stage 306 P1 — data residency pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-residency-pack-rg-pointers.json"


def test_data_residency_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 306 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["multi_region_residency_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "data_residency_stage44",
        "erasure_honesty_pack_remaining_gate_stage305",
        "encryption_kms_stage44",
        "data_portability_pack_remaining_gate",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "drprp-residency-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_data_residency_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/DATA_RESIDENCY_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "DATA_RESIDENCY_MVP.md" in doc
    assert "ERASURE_HONESTY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "ENCRYPTION_KMS_MVP.md" in doc
    assert "DATA_PORTABILITY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "multi_region_residency_claimed" in doc
    assert "schema_per_tenant_claimed" in doc
