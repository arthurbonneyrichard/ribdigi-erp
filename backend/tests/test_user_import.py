"""Bulk user CSV import."""

from __future__ import annotations

import io

import pyotp
import pytest

from app.user_import import template_csv
from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_user_csv_import_dry_run_and_commit(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    tmpl = await ac.get("/api/v1/users/import/template", headers=headers)
    assert tmpl.status_code == 200, tmpl.text
    assert "full_name,email" in tmpl.text
    assert template_csv().startswith("full_name,email")

    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        "Imported One,import1@alpha.example.com,,cashier,,,SecurePass123!,own\n"
        "Bad Row,not-an-email,,cashier,,,,\n"
        "Imported Two,import2@alpha.example.com,,cashier,,,,own\n"
    )
    dry = await ac.post(
        "/api/v1/users/import?dry_run=true",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    data = dry.json()["data"]
    assert data["dry_run"] is True
    assert data["valid_rows"] == 2
    assert data["error_rows"] == 1
    assert data["created"] == []

    committed = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()["data"]
    assert result["valid_rows"] == 2
    assert len(result["created"]) == 2
    emails = {row["email"] for row in result["created"]}
    assert "import1@alpha.example.com" in emails
    assert "import2@alpha.example.com" in emails

    listed = await ac.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200, listed.text
    listed_emails = {u["email"] for u in listed.json()["data"]}
    assert "import1@alpha.example.com" in listed_emails
    assert "import2@alpha.example.com" in listed_emails
