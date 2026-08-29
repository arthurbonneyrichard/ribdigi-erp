"""Bank statement match + clear-group typed bodies OpenAPI (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import BankClearGroupBody, BankStatementMatchBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_A = "11111111-2222-3333-4444-555555555555"
_B = "22222222-3333-4444-5555-666666666666"
_C = "33333333-4444-5555-6666-777777777777"


def test_bank_match_clear_schema_forbid():
    _jl = "11111111-2222-3333-4444-555555555555"
    ok = BankStatementMatchBody.model_validate({"journal_line_id": f"  {_jl}  "})
    assert ok.journal_line_id == _jl

    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({"journal_line_id": ""})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({"journal_line_id": "   "})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({"journal_line_id": "jl-1"})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate(
            {"journal_line_id": _jl, "extra": True}
        )

    group = BankClearGroupBody.model_validate(
        {
            "statement_line_ids": [f"  {_A}  ", "", _B],
            "journal_line_ids": [_C],
            "notes": "ok",
        }
    )
    assert group.statement_line_ids == [_A, _B]
    assert group.journal_line_ids == [_C]

    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {"statement_line_ids": [], "journal_line_ids": [_C]}
        )
    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {"statement_line_ids": [_A], "journal_line_ids": [""]}
        )
    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {"statement_line_ids": ["a"], "journal_line_ids": [_B]}
        )
    with pytest.raises(ValidationError):
        BankClearGroupBody.model_validate(
            {
                "statement_line_ids": [_A],
                "journal_line_ids": [_B],
                "unknown": 1,
            }
        )


def test_bank_match_clear_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "journal_line_id" in page
    assert "clear-group" in page
    assert 'aria-label="Clear selected as group"' in page
    assert 'aria-label="Match bank line to journal line"' in page
    assert "pickBank.map((id) => String(id).trim())" in page
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
        json={"statement_line_ids": [], "journal_line_ids": [_C]},
    )
    assert empty_clear.status_code == 422, empty_clear.text

    unknown_clear = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
        headers=headers,
        json={
            "statement_line_ids": [_A],
            "journal_line_ids": [_B],
            "extra": True,
        },
    )
    assert unknown_clear.status_code == 422, unknown_clear.text
