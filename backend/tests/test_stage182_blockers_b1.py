"""Stage 182 B1 — membership blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "membership-blockers.json"


def test_membership_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 182 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["user_store_membership_claimed"] is False
    assert data["users_store_id_api_claimed"] is False
    assert data["multi_store_membership_claimed"] is False
    assert data["store_scoped_rbac_complete_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr005_membership"] == "DEFERRED"
    assert blockers["users_store_id_api"] == "REMAINING"
    assert blockers["multi_store_membership_table"] == "REMAINING"
    assert blockers["store_scoped_rbac_as_membership"] == "NON_CLAIM"
    assert blockers["user_store_membership_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mb-membership-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_membership_blockers_doc_b1():
    doc = (ROOT / "docs/MEMBERSHIP_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-005" in doc or "ADR_005" in doc
    assert "store_id" in doc or "users.store_id" in doc
    assert "store_scope" in doc.lower() or "Stage 81" in doc
    assert "user_store_membership_claimed" in doc
