"""OpenAPI honesty tips #581–#585: numbering forbid + FE trim/omit."""

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


def test_numbering_forbid_and_fe_omit_schema():
    DocumentNumberingFields.model_validate({"prefix": "JE", "next_number": 1})
    with pytest.raises(ValidationError):
        DocumentNumberingFields.model_validate(
            {"prefix": "JE", "next_number": 1, "junk": True}
        )
    with pytest.raises(ValidationError):
        AccountingSettingsUpdate.model_validate(
            {
                "journal_numbering": {
                    "prefix": "JE",
                    "next_number": 1,
                    "evil": 1,
                }
            }
        )
    SalesSettingsUpdate.model_validate(
        {"invoice_numbering": {"prefix": "INV", "next_number": 2}}
    )
    with pytest.raises(ValidationError):
        SalesSettingsUpdate.model_validate(
            {
                "invoice_numbering": {
                    "prefix": "INV",
                    "next_number": 2,
                    "extra": "nope",
                }
            }
        )


def test_numbering_forbid_fe_omit_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Document numbering nested forbid OpenAPI",
        "Company email Save omit OpenAPI",
        "2FA code FE trim OpenAPI",
        "User phone FE trim OpenAPI",
        "Webhook URL FE trim OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "DocumentNumberingFields` `extra=forbid`" in docs or (
        "DocumentNumberingFields" in docs and "extra=forbid" in docs
    )
    assert "Company email" in docs
    assert "omits blank/whitespace email" in docs or "omits blank" in docs
    assert "hookUrl.trim()" in docs
    assert "form.phone.trim() || null" in docs
    assert "totpCode.trim()" in docs

    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Company email"' in company
    assert "String(tenant.email || '').trim()" in company
    assert "email: String(tenant.email).trim()" in company

    login = (ROOT / "frontend/app/page.tsx").read_text(encoding="utf-8")
    assert "code: totpCode.trim()" in login
    assert "totp_code: totpCode.trim() || null" in login

    security = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "code: code.trim()" in security
    assert security.count("code: code.trim()") >= 2

    users = (ROOT / "frontend/app/users/page.tsx").read_text(encoding="utf-8")
    assert "phone: form.phone.trim() || null" in users

    integrations = (ROOT / "frontend/app/integrations/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "url: hookUrl.trim()" in integrations
    assert 'aria-label="Webhook endpoint URL"' in integrations


@pytest.mark.asyncio
async def test_numbering_nested_forbid_api_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    resp = await ac.patch(
        "/api/v1/accounting/settings",
        headers=headers,
        json={
            "journal_numbering": {
                "prefix": "JE",
                "next_number": 1,
                "junk": True,
            },
            "cash_transfer_numbering": {"prefix": "XFER", "next_number": 1},
        },
    )
    assert resp.status_code == 422, resp.text

    ok = await ac.patch(
        "/api/v1/accounting/settings",
        headers=headers,
        json={
            "journal_numbering": {"prefix": "JE", "next_number": 1},
            "cash_transfer_numbering": {"prefix": "XFER", "next_number": 1},
        },
    )
    assert ok.status_code == 200, ok.text
