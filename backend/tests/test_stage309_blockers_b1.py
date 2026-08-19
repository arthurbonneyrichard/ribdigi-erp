"""Stage 309 B1 — data retention return pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-retention-return-pack-rg-blockers.json"


def test_data_retention_return_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 309 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["data_return_portal_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["data_return_portal_claimed"] == "REMAINING"
    assert blockers["hot_audit_purge_claimed"] == "REMAINING"
    assert blockers["contract_exit_return_live"] == "REMAINING"
    assert blockers["offboarding_workflow_claimed"] == "REMAINING"
    assert blockers["stage45_as_data_return_portal"] == "NON_CLAIM"
    assert blockers["data_return_portal_claimed_flag"] == "false"
    assert blockers["hot_audit_purge_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "drrpb-portal-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_data_retention_return_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/DATA_RETENTION_RETURN_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "data_return_portal_claimed" in doc
    assert "hot_audit_purge_claimed" in doc
    assert "Stage 45" in doc
