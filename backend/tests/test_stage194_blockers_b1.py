"""Stage 194 B1 — first-tenant live onboarding blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-live-onboarding-blockers.json"


def test_first_tenant_live_onboarding_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 194 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["live_onboarding_success_claimed"] is False
    assert data["first_paying_tenant_claimed"] is False
    assert data["demo_tenant_claimed"] is False
    blockers = data["blockers"]
    assert blockers["live_onboarding_success"] == "REMAINING"
    assert blockers["first_tenant_onboarded"] == "REMAINING"
    assert blockers["first_paying_tenant"] == "REMAINING"
    assert blockers["stage33_f1_as_live_onboarding"] == "NON_CLAIM"
    assert blockers["stage66_t1_as_live_onboarding"] == "NON_CLAIM"
    assert blockers["live_onboarding_success_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "fb-onboarding-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_live_onboarding_blockers_doc_b1():
    doc = (ROOT / "docs/FIRST_TENANT_LIVE_ONBOARDING_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "live_onboarding_success_claimed" in doc
    assert "Stage 33" in doc
    assert "Stage 66" in doc
