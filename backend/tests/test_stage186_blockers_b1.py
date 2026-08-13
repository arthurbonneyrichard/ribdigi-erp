"""Stage 186 B1 — audit-retention blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "audit-retention-blockers.json"


def test_audit_retention_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 186 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["hot_audit_purge_claimed"] is False
    assert data["hot_row_physical_delete_claimed"] is False
    assert data["cold_archive_as_purge_claimed"] is False
    assert data["infinite_retention_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr007_hot_table_pruning"] == "DEFERRED"
    assert blockers["purge_api"] == "REMAINING"
    assert blockers["cold_archive_as_purge"] == "NON_CLAIM"
    assert blockers["infinite_retention_complete"] == "NON_CLAIM"
    assert blockers["hot_audit_purge_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ab-purge-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_audit_retention_blockers_doc_b1():
    doc = (ROOT / "docs/AUDIT_RETENTION_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-007" in doc or "ADR_007" in doc
    assert "purge" in doc.lower()
    assert "cold" in doc.lower()
    assert "hot_audit_purge_claimed" in doc
