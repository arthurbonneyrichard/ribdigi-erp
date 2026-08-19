"""Stage 363 B1 — E2E users RBAC pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-users-rbac-pack-rg-blockers.json"


def test_e2e_users_rbac_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 363 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["live_users_provisioned_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_users_provisioned_claimed"] == "REMAINING"
    assert blockers["e2e_smoke_executed_claimed"] == "REMAINING"
    assert blockers["demo_tenant_claimed"] == "REMAINING"
    assert blockers["store_membership_claimed"] == "REMAINING"
    assert blockers["go_live_claimed"] == "REMAINING"
    assert blockers["stage35_as_live_e2e_users_rbac"] == "NON_CLAIM"
    assert blockers["live_users_provisioned_claimed_flag"] == "false"
    assert blockers["go_live_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "eurbprb-checklist-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_e2e_users_rbac_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/E2E_USERS_RBAC_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "live_users_provisioned_claimed" in doc
    assert "store_membership_claimed" in doc
    assert "Stage 35" in doc
