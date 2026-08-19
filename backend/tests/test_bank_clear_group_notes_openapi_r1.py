"""BankClearGroupBody.notes OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import BankClearGroupBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_clear_group_notes_schema():
    omit = BankClearGroupBody.model_validate(
        {"statement_line_ids": ["a"], "journal_line_ids": ["b"]}
    )
    assert omit.notes is None
    nullish = BankClearGroupBody.model_validate(
        {"statement_line_ids": ["a"], "journal_line_ids": ["b"], "notes": None}
    )
    assert nullish.notes is None
    ok = BankClearGroupBody.model_validate(
        {
            "statement_line_ids": ["a"],
            "journal_line_ids": ["b"],
            "notes": "  Split deposit clear  ",
        }
    )
    assert ok.notes == "Split deposit clear"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BankClearGroupBody.model_validate(
                {
                    "statement_line_ids": ["a"],
                    "journal_line_ids": ["b"],
                    "notes": bad,
                }
            )


def test_bank_clear_group_notes_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Clear-group notes"' in page
    assert "clearGroupNotes.trim() || null" in page
    assert 'aria-label="Clear selected as group"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank clear-group notes OpenAPI" in agents
    assert "BankClearGroupNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankClearGroupNotesValue" in docs
    assert "Clear-group notes" in docs


@pytest.mark.asyncio
async def test_bank_clear_group_notes_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    statement_id = "00000000-0000-0000-0000-000000000099"
    suffix = uuid4().hex[:8]

    # Body validation runs before resource lookup — blank/invalid notes → 422.
    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
            headers=headers,
            json={
                "statement_line_ids": ["a"],
                "journal_line_ids": ["b"],
                "notes": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    # Valid notes shape still fails later on missing statement (not 422 for notes).
    ok_notes_bad_resource = await ac.post(
        f"/api/v1/accounting/bank-statements/{statement_id}/clear-group",
        headers=headers,
        json={
            "statement_line_ids": ["a"],
            "journal_line_ids": ["b"],
            "notes": f"  Tip167 notes {suffix}  ",
        },
    )
    assert ok_notes_bad_resource.status_code != 422, ok_notes_bad_resource.text
    assert ok_notes_bad_resource.status_code in (404, 400, 409), ok_notes_bad_resource.text
