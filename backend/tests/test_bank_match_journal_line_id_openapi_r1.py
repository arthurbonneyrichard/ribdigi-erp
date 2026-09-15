"""BankStatementMatchBody.journal_line_id ∈ UuidIdValue OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BankStatementMatchBody, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_bank_match_journal_line_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = BankStatementMatchBody.model_validate({"journal_line_id": f"  {_VALID}  "})
    assert ok.journal_line_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "jl-1"):
        with pytest.raises(ValidationError):
            BankStatementMatchBody.model_validate({"journal_line_id": bad})
    with pytest.raises(ValidationError):
        BankStatementMatchBody.model_validate({})


def test_bank_match_journal_line_id_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "journal_line_id: String(journalLineId).trim()" in page
    assert 'aria-label="Match bank line to journal line"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank match journal_line_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankStatementMatchBody" in docs
    assert "UuidIdValue" in docs


@pytest.mark.asyncio
async def test_bank_match_journal_line_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    statement_id = str(uuid4())
    line_id = str(uuid4())
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "jl-1"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/{statement_id}/lines/{line_id}/match",
            headers=headers,
            json={"journal_line_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/lines/{line_id}/match",
        headers=headers,
        json={"journal_line_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
