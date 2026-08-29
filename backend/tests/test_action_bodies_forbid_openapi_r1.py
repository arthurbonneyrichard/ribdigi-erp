"""OpenAPI honesty tips #571–#575: final action-body extra=forbid sweep."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExpenseDecision,
    JournalUnpost,
    PlatformGrantAccess,
    PlatformRevokeAccess,
    PosDrawerOpen,
    PosSessionClose,
    PosSessionOpen,
    RecurringSkipNext,
    TenantSubscriptionAssign,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ID = str(uuid4())


def test_action_bodies_forbid_schema():
    TenantSubscriptionAssign.model_validate(
        {"package_code": "starter", "term_value": 12}
    )
    with pytest.raises(ValidationError):
        TenantSubscriptionAssign.model_validate(
            {"package_code": "starter", "term_value": 12, "evil": 1}
        )

    PlatformGrantAccess.model_validate({"user_id": _ID})
    with pytest.raises(ValidationError):
        PlatformGrantAccess.model_validate({"user_id": _ID, "evil": 1})
    PlatformRevokeAccess.model_validate({})
    with pytest.raises(ValidationError):
        PlatformRevokeAccess.model_validate({"evil": 1})

    ExpenseDecision.model_validate({})
    ExpenseDecision.model_validate({"comment": "Looks good"})
    with pytest.raises(ValidationError):
        ExpenseDecision.model_validate({"comment": "Looks good", "evil": 1})
    RecurringSkipNext.model_validate({"reason": "Supplier delay"})
    with pytest.raises(ValidationError):
        RecurringSkipNext.model_validate({"reason": "Supplier delay", "evil": 1})

    PosDrawerOpen.model_validate({"reason": "Cash check"})
    with pytest.raises(ValidationError):
        PosDrawerOpen.model_validate({"reason": "Cash check", "evil": 1})
    PosSessionOpen.model_validate({"opening_cash": 100})
    with pytest.raises(ValidationError):
        PosSessionOpen.model_validate({"opening_cash": 100, "evil": 1})
    PosSessionClose.model_validate({"actual_cash": 100})
    with pytest.raises(ValidationError):
        PosSessionClose.model_validate({"actual_cash": 100, "evil": 1})

    JournalUnpost.model_validate({"reason": "Posted to wrong period"})
    with pytest.raises(ValidationError):
        JournalUnpost.model_validate(
            {"reason": "Posted to wrong period", "evil": 1}
        )


def test_action_bodies_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Tenant subscription assign body OpenAPI",
        "Platform grant/revoke access bodies OpenAPI",
        "Expense decision / recurring skip bodies OpenAPI",
        "POS drawer / session bodies OpenAPI",
        "Journal unpost body OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "TenantSubscriptionAssign" in docs
    assert "PlatformGrantAccess" in docs
    assert "PlatformRevokeAccess" in docs
    assert "ExpenseDecision" in docs
    assert "RecurringSkipNext" in docs
    assert "PosSessionOpen" in docs
    assert "PosSessionClose" in docs
    assert "PosDrawerOpen" in docs
    assert "JournalUnpost" in docs

    assert 'aria-label="Grant dashboard"' in (
        ROOT / "frontend/app/platform/staff/page.tsx"
    ).read_text(encoding="utf-8")
    assert 'aria-label="Skip next reason"' in (
        ROOT / "frontend/app/expenses/page.tsx"
    ).read_text(encoding="utf-8")
    assert 'aria-label="Journal unpost reason"' in (
        ROOT / "frontend/app/accounting/page.tsx"
    ).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_action_bodies_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 50, "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        f"/api/v1/expenses/{_ID}/approve",
        headers=headers,
        json={"comment": "ok", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        f"/api/v1/accounting/journal-entries/{_ID}/unpost",
        headers=headers,
        json={"reason": "Wrong period", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        f"/api/v1/pos/sessions/{_ID}/drawer/open",
        headers=headers,
        json={"reason": "Cash check", "evil": True},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        f"/api/v1/expenses/recurring/{_ID}/skip-next",
        headers=headers,
        json={"reason": "Supplier delay", "evil": True},
    )
    assert resp.status_code == 422, resp.text
