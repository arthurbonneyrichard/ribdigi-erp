"""Stage 307 P1 — encryption KMS pack RG pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "encryption-kms-pack-rg-pointers.json"


def test_encryption_kms_pack_rg_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 307 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["hsm_claimed"] is False
    assert data["go_live_claimed"] is False
    for topic in (
        "encryption_kms_stage44",
        "data_residency_pack_remaining_gate_stage306",
        "data_residency_stage44",
        "erasure_honesty_pack_remaining_gate_stage305",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ekprp-hsm-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_encryption_kms_pack_rg_pointers_doc_p1():
    doc = (ROOT / "docs/ENCRYPTION_KMS_PACK_RG_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ENCRYPTION_KMS_MVP.md" in doc
    assert "DATA_RESIDENCY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "DATA_RESIDENCY_MVP.md" in doc
    assert "ERASURE_HONESTY_PACK_REMAINING_GATE_MVP.md" in doc
    assert "hsm_claimed" in doc
    assert "customer_managed_keys_claimed" in doc
