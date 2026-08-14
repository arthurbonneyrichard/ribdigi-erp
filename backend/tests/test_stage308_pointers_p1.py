"""Stage 308 P1 — RTO/RPO pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "rto-rpo-pack-rg-pointers.json"


def test_rto_rpo_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 308 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["measured_rto_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "rto_rpo_stage45",
        "encryption_kms_pack_remaining_gate_stage307",
        "data_residency_pack_remaining_gate_stage306",
        "data_retention_return_stage45",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "rrprp-rto-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_rto_rpo_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/RTO_RPO_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "RTO_RPO_MVP.md" in doc
    assert "ENCRYPTION_KMS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DATA_RESIDENCY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DATA_RETENTION_RETURN_MVP.md" in doc
    assert "measured_rto_claimed" in doc
    assert "measured_rpo_claimed" in doc
