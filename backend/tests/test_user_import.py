"""User CSV bulk import — template, validation, commit, tenant isolation."""

from __future__ import annotations

import pyotp
import pytest

from app.user_import import parse_csv_rows, template_csv
from tests.conftest import auth_headers


async def _admin(ac, seeded):
    code = pyotp.TOTP(seeded["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_user_template_headers():
    text = template_csv()
    header = text.splitlines()[0]
    assert "full_name" in header
    assert "email" in header
    assert "role" in header
    assert "temporary_password" in header


def test_parse_accepts_password_alias():
    rows = parse_csv_rows(
        "full_name,email,role,password\nAda,ada@alpha.example.com,cashier,TempPass1!\n"
    )
    assert rows[0]["temporary_password"] == "TempPass1!"


@pytest.mark.asyncio
async def test_user_import_dry_run_and_commit(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)

    csv_ok = (
        "full_name,email,phone,role,temporary_password\n"
        "Import Cashier One,import.cashier1@alpha.example.com,,cashier,TempPass1!\n"
        "Import Officer,import.io1@alpha.example.com,+233200000001,inventory_officer,TempPass1!\n"
    )
    dry = await ac.post(
        "/api/v1/users/import?dry_run=true",
        headers=admin,
        files={"file": ("users.csv", csv_ok, "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    report = dry.json()["data"]
    assert report["can_commit"] is True
    assert report["valid_rows"] == 2

    listed_before = await ac.get("/api/v1/users", headers=admin)
    emails_before = {u["email"] for u in listed_before.json()["data"]}
    assert "import.cashier1@alpha.example.com" not in emails_before

    commit = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=admin,
        files={"file": ("users.csv", csv_ok, "text/csv")},
    )
    assert commit.status_code == 200, commit.text
    body = commit.json()["data"]
    assert body["imported"] == 2

    listed = await ac.get("/api/v1/users", headers=admin)
    by_email = {u["email"]: u for u in listed.json()["data"]}
    assert by_email["import.cashier1@alpha.example.com"]["role"] == "cashier"
    assert by_email["import.io1@alpha.example.com"]["role"] == "inventory_officer"


@pytest.mark.asyncio
async def test_user_import_rejects_duplicate_and_bad_role(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)

    csv_bad = (
        "full_name,email,role,temporary_password\n"
        "Dup,cashier@alpha.example.com,cashier,TempPass1!\n"
        "Bad Role,badrole@alpha.example.com,wizard,TempPass1!\n"
        "Weak,weak@alpha.example.com,cashier,password\n"
    )
    dry = await ac.post(
        "/api/v1/users/import?dry_run=true",
        headers=admin,
        files={"file": ("bad.csv", csv_bad, "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    report = dry.json()["data"]
    assert report["can_commit"] is False
    assert report["error_rows"] == 3
    errs = " | ".join(";".join(r["errors"]) for r in report["rows"])
    assert "email already exists" in errs
    assert "unknown role" in errs
    assert "Password must" in errs

    commit = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=admin,
        files={"file": ("bad.csv", csv_bad, "text/csv")},
    )
    assert commit.status_code == 400
    assert commit.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_user_import_tenant_isolation(client):
    ac, seeded = client
    admin = await _admin(ac, seeded)
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    csv_alpha = (
        "full_name,email,role,temporary_password\n"
        "Alpha Only,alpha.only@alpha.example.com,cashier,TempPass1!\n"
    )
    r = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=admin,
        files={"file": ("a.csv", csv_alpha, "text/csv")},
    )
    assert r.status_code == 200, r.text

    # Beta cashier lacks users:read typically — either 403 or empty of alpha email
    listed = await ac.get("/api/v1/users", headers=beta)
    if listed.status_code == 200:
        emails = {u["email"] for u in listed.json()["data"]}
        assert "alpha.only@alpha.example.com" not in emails
    else:
        assert listed.status_code == 403
