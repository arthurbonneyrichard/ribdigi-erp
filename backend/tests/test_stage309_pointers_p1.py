"""Stage 309 P1 — data retention return pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-retention-return-pack-rg-pointers.json"


def test_data_retention_return_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 309 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["data_return_portal_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "data_retention_return_stage45",
        "rto_rpo_pack_remaining_gate_stage308",
        "encryption_kms_pack_remaining_gate_stage307",
        "audit_retention_remaining_gate_stage186",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "drrpp-portal-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_data_retention_return_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/DATA_RETENTION_RETURN_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "DATA_RETENTION_RETURN_MVP.md" in doc
    assert "RTO_RPO_PACK_REMAINING_GATE_MVP.md" in doc
    assert "ENCRYPTION_KMS_PACK_REMAINING_GATE_MVP.md" in doc
    assert "AUDIT_RETENTION_REMAINING_GATE_MVP.md" in doc
    assert "data_return_portal_claimed" in doc
    assert "hot_audit_purge_claimed" in doc
