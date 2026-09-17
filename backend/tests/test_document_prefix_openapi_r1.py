"""DocumentNumberingFields.prefix OpenAPI honesty (BR-20.4)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import (
    AccountingSettingsUpdate,
    DocumentNumberingFields,
    SalesSettingsUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_document_prefix_schema():
    ok = DocumentNumberingFields.model_validate({"prefix": " je ", "next_number": 2})
    assert ok.prefix == "JE"
    assert ok.next_number == 2
    assert DocumentNumberingFields.model_validate({"prefix": "XFER"}).prefix == "XFER"
    assert DocumentNumberingFields.model_validate({"prefix": "PO_1"}).prefix == "PO_1"
    for bad in ("", " ", "!!!", "JE!", "a b", "http://x", "-JE", "_X"):
        with pytest.raises(ValidationError):
            DocumentNumberingFields.model_validate({"prefix": bad})

    acct = AccountingSettingsUpdate.model_validate(
        {"journal_numbering": {"prefix": "je", "next_number": 1}}
    )
    assert acct.journal_numbering and acct.journal_numbering.prefix == "JE"

    legacy = SalesSettingsUpdate.model_validate({"prefix": " inv "})
    assert legacy.prefix == "INV"
    with pytest.raises(ValidationError):
        SalesSettingsUpdate.model_validate({"prefix": "!!!"})


def test_document_prefix_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Journal number prefix"' in page
    assert 'aria-label="Cash transfer number prefix"' in page
    assert 'aria-label="Save accounting numbering"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Document numbering prefix OpenAPI" in agents
    assert "DocumentPrefixValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "DocumentPrefixValue" in docs
    assert "Journal number prefix" in docs


@pytest.mark.asyncio
async def test_document_prefix_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    for bad in ("", "!!!", "JE!"):
        resp = await ac.patch(
            "/api/v1/accounting/settings",
            headers=headers,
            json={
                "journal_numbering": {"prefix": bad, "next_number": 1},
                "cash_transfer_numbering": {"prefix": "XFER", "next_number": 1},
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.patch(
        "/api/v1/accounting/settings",
        headers=headers,
        json={
            "journal_numbering": {"prefix": " je ", "next_number": 7},
            "cash_transfer_numbering": {"prefix": "xfer", "next_number": 3},
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["journal_numbering"]["prefix"] == "JE"
    assert data["journal_numbering"]["next_number"] == 7
    assert str(data["journal_numbering"]["preview"]).startswith("JE-")
    assert data["cash_transfer_numbering"]["prefix"] == "XFER"
    assert data["cash_transfer_numbering"]["next_number"] == 3
