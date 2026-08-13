"""Stage 186 P1 — audit-retention pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "audit-retention-pack-pointers.json"


def test_audit_retention_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 186 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["hot_audit_purge_claimed"] is False
    assert data["hot_row_physical_delete_claimed"] is False
    assert data["cold_archive_as_purge_claimed"] is False
    for topic in (
        "adr007_audit_retention",
        "data_retention_return",
        "commercial_data_retention",
        "schema_per_tenant_remaining_gate_stage185",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ap-purge-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_audit_retention_pack_pointers_doc_p1():
    doc = (ROOT / "docs/AUDIT_RETENTION_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_007_AUDIT_RETENTION.md" in doc
    assert "DATA_RETENTION_RETURN_MVP.md" in doc
    assert "COMMERCIAL_DATA_RETENTION_MVP.md" in doc
    assert "hot_audit_purge_claimed" in doc
