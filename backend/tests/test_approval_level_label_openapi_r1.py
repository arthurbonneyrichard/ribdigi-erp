"""Approval matrix level label OpenAPI honesty (BR-9.3 / PR)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ApprovalLevelUpdate, PurchaseApprovalLevelUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_approval_level_label_schema():
    omit = ApprovalLevelUpdate.model_validate(
        {"min_amount": 50, "roles": ["store_manager"]}
    )
    assert omit.label is None
    ok = ApprovalLevelUpdate.model_validate(
        {"min_amount": 50, "roles": ["store_manager"], "label": "  Manager review  "}
    )
    assert ok.label == "Manager review"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            ApprovalLevelUpdate.model_validate(
                {"min_amount": 50, "roles": ["store_manager"], "label": bad}
            )

    pr_ok = PurchaseApprovalLevelUpdate.model_validate(
        {"roles": ["company_admin"], "label": "  Company Admin  "}
    )
    assert pr_ok.label == "Company Admin"
    with pytest.raises(ValidationError):
        PurchaseApprovalLevelUpdate.model_validate(
            {"roles": ["company_admin"], "label": "!!!!"}
        )


def test_approval_level_label_ui_and_docs():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`Expense approval level ${idx + 1} label`}' in expenses
    assert "(l.label || '').trim() || null" in expenses
    assert 'aria-label="Save expense approval matrix"' in expenses
    assert 'aria-label={`PR approval level ${idx + 1} label`}' in purchasing
    assert "(l.label || '').trim() || null" in purchasing
    assert 'aria-label="Save PR approval matrix"' in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ApprovalLevelLabelValue" in agents
    assert "Approval matrix label OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ApprovalLevelLabelValue" in docs


@pytest.mark.asyncio
async def test_approval_level_label_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP189 L1 {suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.patch(
            "/api/v1/expenses/settings",
            headers=headers,
            json={
                "levels": [
                    {
                        "min_amount": 50,
                        "roles": ["store_manager"],
                        "label": bad,
                    }
                ]
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.patch(
        "/api/v1/expenses/settings",
        headers=headers,
        json={
            "levels": [
                {
                    "min_amount": 50,
                    "roles": ["store_manager"],
                    "label": tag,
                }
            ]
        },
    )
    assert ok.status_code == 200, ok.text
    levels = (ok.json().get("data") or {}).get("levels") or []
    assert levels and levels[0].get("label") == tag

    pr_bad = await ac.patch(
        "/api/v1/purchasing/requests/settings",
        headers=headers,
        json={"levels": [{"roles": ["store_manager"], "label": "!!!!"}]},
    )
    assert pr_bad.status_code == 422, pr_bad.text

    pr_ok = await ac.patch(
        "/api/v1/purchasing/requests/settings",
        headers=headers,
        json={
            "levels": [
                {"roles": ["store_manager"], "label": f"PR {tag}"},
                {"roles": ["company_admin"], "label": "Company Admin"},
            ]
        },
    )
    assert pr_ok.status_code == 200, pr_ok.text
    pr_levels = (pr_ok.json().get("data") or {}).get("levels") or []
    assert any(l.get("label") == f"PR {tag}" for l in pr_levels)
