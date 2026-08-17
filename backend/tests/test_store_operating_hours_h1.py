"""Store operating hours (BR-2.3)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_store_operating_hours_create_patch_and_validation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    hours = {
        "mon": {"open": "09:00", "close": "18:00"},
        "tue": {"open": "09:00", "close": "18:00"},
        "wed": {"open": "09:00", "close": "18:00"},
        "thu": {"open": "09:00", "close": "18:00"},
        "fri": {"open": "09:00", "close": "17:00"},
        "sat": {"closed": True},
        "sun": {"closed": True},
    }
    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "name": "Hours Store",
            "code": "HRS-1",
            "address": "12 High St",
            "operating_hours": hours,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["operating_hours"]["mon"]["open"] == "09:00"
    assert data["operating_hours"]["mon"]["closed"] is False
    assert data["operating_hours"]["sat"] == {"closed": True}
    sid = data["id"]

    # transfers list must not be captured by GET /stores/{id}
    transfers = await ac.get("/api/v1/stores/transfers", headers=headers)
    assert transfers.status_code == 200

    got = await ac.get(f"/api/v1/stores/{sid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["operating_hours"]["fri"]["close"] == "17:00"

    patched = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={
            "operating_hours": {
                "mon": {"open": "08:30", "close": "20:00"},
                "sun": {"closed": True},
            }
        },
    )
    assert patched.status_code == 200, patched.text
    ph = patched.json()["data"]["operating_hours"]
    assert ph["mon"]["open"] == "08:30"
    assert "tue" not in ph
    assert ph["sun"]["closed"] is True

    bad_day = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"operating_hours": {"monday": {"open": "09:00", "close": "17:00"}}},
    )
    assert bad_day.status_code == 422

    bad_order = await ac.patch(
        f"/api/v1/stores/{sid}",
        headers=headers,
        json={"operating_hours": {"mon": {"open": "18:00", "close": "09:00"}}},
    )
    assert bad_order.status_code == 422
