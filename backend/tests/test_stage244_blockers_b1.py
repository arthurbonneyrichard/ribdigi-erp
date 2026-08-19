"""Stage 244 B1 — first-tenant onboarding pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-onboarding-pack-rg-blockers.json"


def test_first_tenant_onboarding_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 244 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["live_onboarding_success_claimed"] is False
    assert data["first_paying_tenant_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_onboarding_delivery_execution"] == "REMAINING"
    assert blockers["first_paying_tenant_complete"] == "REMAINING"
    assert blockers["stage33_f1_as_live_onboarding"] == "NON_CLAIM"
    assert blockers["stage194_i1_as_live_onboarding"] == "NON_CLAIM"
    assert blockers["stage66_t1_as_live_onboarding"] == "NON_CLAIM"
    assert blockers["first_tenant_onboarded_claimed"] == "false"
    assert blockers["live_onboarding_success_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ftoprb-onboarding-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_onboarding_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/FIRST_TENANT_ONBOARDING_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "first_tenant_onboarded_claimed" in doc
    assert "live_onboarding_success_claimed" in doc
    assert "Stage 33" in doc
