"""Tenant date/number/time formatting preferences (BR-20.2)."""

from __future__ import annotations

import pyotp
import pytest
from fastapi import HTTPException

from app import models as m
from app.tenants import serialize_tenant, update_profile
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_serialize_tenant_formatting_defaults():
    tenant = m.Tenant(slug="fmt", company_name="Fmt Co", status="active")
    data = serialize_tenant(tenant)
    assert data["date_format"] == "DD/MM/YYYY"
    assert data["decimal_separator"] == "."
    assert data["thousand_separator"] == ","
    assert data["time_format"] == "24h"


@pytest.mark.asyncio
async def test_update_profile_formatting_and_reject_same_separators(db_session):
    row = m.Tenant(slug="fmt-unit", company_name="Unit Fmt", status="active")
    db_session.add(row)
    await db_session.flush()

    updated = await update_profile(
        db_session,
        row,
        date_format="YYYY-MM-DD",
        decimal_separator=",",
        thousand_separator=".",
        time_format="12h",
    )
    assert updated.date_format == "YYYY-MM-DD"
    assert updated.decimal_separator == ","
    assert updated.thousand_separator == "."
    assert updated.time_format == "12h"

    none_sep = await update_profile(db_session, updated, thousand_separator="none")
    assert none_sep.thousand_separator == ""

    with pytest.raises(HTTPException) as ei:
        await update_profile(
            db_session,
            none_sep,
            decimal_separator=",",
            thousand_separator=",",
        )
    assert ei.value.status_code == 400

    with pytest.raises(HTTPException) as ei2:
        await update_profile(db_session, none_sep, date_format="YY/MM/DD")
    assert ei2.value.status_code == 400


@pytest.mark.asyncio
async def test_formatting_patch_get_and_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    got = await ac.get("/api/v1/tenants/me", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["date_format"] == "DD/MM/YYYY"

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "date_format": "MM/DD/YYYY",
            "decimal_separator": ",",
            "thousand_separator": " ",
            "time_format": "12h",
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["date_format"] == "MM/DD/YYYY"
    assert data["decimal_separator"] == ","
    assert data["thousand_separator"] == " "
    assert data["time_format"] == "12h"

    again = await ac.get("/api/v1/tenants/me", headers=headers)
    assert again.json()["data"]["date_format"] == "MM/DD/YYYY"

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"decimal_separator": ".", "thousand_separator": "."},
    )
    assert bad.status_code == 400

    # Mismatched X-Tenant-ID must not return another tenant's profile.
    foreign = await ac.get(
        "/api/v1/tenants/me",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert foreign.status_code == 403
