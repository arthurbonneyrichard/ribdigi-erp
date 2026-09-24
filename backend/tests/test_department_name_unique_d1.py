"""Department name uniqueness, search, and default seed list."""

from __future__ import annotations

import pyotp
import pytest

from app.org_units import DEFAULT_DEPARTMENTS
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_department_name_unique_within_tenant(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    first = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "SALES1", "name": "Front of House"},
    )
    assert first.status_code == 200, first.text
    dup = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "SALES2", "name": "front of house"},
    )
    assert dup.status_code == 409, dup.text

    other = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    steal = await ac.patch(
        f"/api/v1/departments/{first.json()['data']['id']}",
        headers=other,
        json={"name": "Hacked"},
    )
    assert steal.status_code in (401, 403, 404)

    listed = await ac.get("/api/v1/departments?q=Front", headers=headers)
    assert listed.status_code == 200
    names = [r["name"] for r in listed.json()["data"]]
    assert any(n.lower() == "front of house" for n in names)


def test_default_department_catalog_covers_requested_names():
    names = {n for _, n in DEFAULT_DEPARTMENTS}
    for expected in (
        "Sales",
        "Inventory",
        "Purchasing",
        "Warehouse",
        "Finance",
        "Accounting",
        "Human Resources",
        "Production",
        "Operations",
        "Customer Service",
        "Information Technology",
        "Administration",
        "Marketing",
    ):
        assert expected in names
