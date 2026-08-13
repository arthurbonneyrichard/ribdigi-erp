"""Stage 182 P1 — membership pack pointers packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "membership-pack-pointers.json"


def test_membership_pack_pointers_register_p1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 182 and data["pack"] == "P1"
    assert data["packaging_complete"] is True
    assert data["user_store_membership_claimed"] is False
    assert data["users_store_id_api_claimed"] is False
    assert data["store_membership_claimed"] is False
    for topic in (
        "adr005_user_store_assignment",
        "e2e_users_rbac",
        "deferred_adr_register",
        "stage81_store_scope_adjacency",
        "explicit_non_claim",
    ):
        assert topic in data["topics"], topic
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "mp-membership-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_membership_pack_pointers_doc_p1():
    doc = (ROOT / "docs/MEMBERSHIP_PACK_POINTERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR_005_USER_STORE_ASSIGNMENT.md" in doc
    assert "E2E_USERS_RBAC_MVP.md" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "user_store_membership_claimed" in doc
