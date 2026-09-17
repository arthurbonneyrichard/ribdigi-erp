"""BankClearGroupBody.journal_line_ids ∈ list[UuidIdValue] OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankClearGroupBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_A = "11111111-2222-3333-4444-555555555555"
_B = "22222222-3333-4444-5555-666666666666"


def test_bank_clear_group_journal_line_ids_schema():
    ok = BankClearGroupBody.model_validate(
        {
            "statement_line_ids": [_A],
            "journal_line_ids": [f"  {_B}  ", ""],
        }
    )
    assert ok.journal_line_ids == [_B]
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "jl-1"):
        with pytest.raises(ValidationError):
            BankClearGroupBody.model_validate(
                {"statement_line_ids": [_A], "journal_line_ids": [bad]}
            )


def test_bank_clear_group_journal_line_ids_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "pickBook.map((id) => String(id).trim())" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank clear-group journal_line_ids OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "list[UuidIdValue]" in docs
    assert "journal_line_ids" in docs


@pytest.mark.asyncio
async def test_bank_clear_group_journal_line_ids_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    statement_id = str(uuid4())
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "jl-1"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
            headers=headers,
            json={"statement_line_ids": [_A], "journal_line_ids": [bad]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
        headers=headers,
        json={
            "statement_line_ids": [f"  {str(uuid4()).upper()}  "],
            "journal_line_ids": [f"  {str(uuid4()).upper()}  "],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
