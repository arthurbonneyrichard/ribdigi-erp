"""Bank statement match + clear-group typed bodies OpenAPI (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BankClearGroupBody, BankStatementMatchBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_match_clear_schema_forbid():
    ok = BankStatementMatchBody.model_validate({"journal_line_id": "  jl-1  "})
    assert ok.journal_line_id == "jl-1"

    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({"journal_line_id": ""})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({"journal_line_id": "   "})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate(
            {"journal_line_id": "jl-1", "extra": True}
        )

    group = BankClearGroupBody.model_validate(
        {
            "statement_line_ids": ["  a  ", "", "b"],
            "journal_line_ids": ["c"],
            "notes": "ok",
        }
    )
    assert group.statement_line_ids == ["a", "b"]
    assert group.journal_line_ids == ["c"]

    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {"statement_line_ids": [], "journal_line_ids": ["c"]}
        )
    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {"statement_line_ids": ["a"], "journal_line_ids": [""]}
        )
    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {
                "statement_line_ids": ["a"],
                "journal_line_ids": ["b"],
                "unknown": 1,
            }
        )


def test_bank_match_clear_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "journal_line_id" in page
    assert "clear-group" in page
    assert 'aria-label="Clear selected as group"' in page
    assert 'aria-label="Match bank line to journal line"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank recon match/clear-group OpenAPI" in agents
    assert "BankStatementMatchBody" in agents
    assert "BankClearGroupBody" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementMatchBody" in docs
    assert "BankClearGroupBody" in docs
    assert "extra=forbid" in docs


@pytest.mark.asyncio
async def test_bank_match_clear_api_unknown_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    statement_id = "00000000-0000-0000-0000-000000000099"
    line_id = "00000000-0000-0000-0000-000000000098"

    # Body validation runs before resource lookup — unknown/blank → 422.
    unknown_match = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/lines/{line_id}/match",
        headers=headers,
        json={"journal_line_id": "jl-x", "foo": 1},
    )
    assert unknown_match.status_code == 422, unknown_match.text

    blank_match = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/lines/{line_id}/match",
        headers=headers,
        json={"journal_line_id": ""},
    )
    assert blank_match.status_code == 422, blank_match.text

    omit_match = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/lines/{line_id}/match",
        headers=headers,
        json={},
    )
    assert omit_match.status_code == 422, omit_match.text

    empty_clear = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
        headers=headers,
        json={"statement_line_ids": [], "journal_line_ids": ["jl-x"]},
    )
    assert empty_clear.status_code == 422, empty_clear.text

    unknown_clear = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
        headers=headers,
        json={
            "statement_line_ids": ["a"],
            "journal_line_ids": ["b"],
            "extra": True,
        },
    )
    assert unknown_clear.status_code == 422, unknown_clear.text
