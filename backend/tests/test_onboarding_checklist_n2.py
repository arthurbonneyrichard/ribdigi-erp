"""Stage 6 N2: tenant onboarding checklist API."""

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
async def test_onboarding_checklist_progress_skip_dismiss(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    res = await ac.get("/api/v1/onboarding/checklist", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["total_count"] == 5
    assert data["visible"] is True
    assert data["dismissed"] is False
    assert data["progress_pct"] < 80
    assert data["dismissible"] is False

    by_id = {s["id"]: s for s in data["steps"]}
    # Seed has product + stock for alpha; company profile / supplier / sale still open.
    assert by_id["add_products"]["auto_completed"] is True
    assert by_id["stock_ready"]["auto_completed"] is True
    assert by_id["setup_company"]["auto_completed"] is False
    assert by_id["create_supplier"]["auto_completed"] is False
    assert by_id["first_sale"]["auto_completed"] is False

    early = await ac.post("/api/v1/onboarding/checklist/dismiss", headers=headers)
    assert early.status_code == 400

    skip1 = await ac.post(
        "/api/v1/onboarding/checklist/steps/setup_company/skip", headers=headers
    )
    assert skip1.status_code == 200, skip1.text
    skip2 = await ac.post(
        "/api/v1/onboarding/checklist/steps/create_supplier/skip", headers=headers
    )
    assert skip2.status_code == 200, skip2.text
    mid = skip2.json()["data"]
    assert mid["progress_pct"] >= 80
    assert mid["dismissible"] is True

    bad_step = await ac.post(
        "/api/v1/onboarding/checklist/steps/not_a_step/skip", headers=headers
    )
    assert bad_step.status_code == 400

    dismissed = await ac.post("/api/v1/onboarding/checklist/dismiss", headers=headers)
    assert dismissed.status_code == 200, dismissed.text
    ddata = dismissed.json()["data"]
    assert ddata["dismissed"] is True
    assert ddata["visible"] is False

    restored = await ac.post("/api/v1/onboarding/checklist/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    rdata = restored.json()["data"]
    assert rdata["dismissed"] is False
    assert rdata["visible"] is True

    unskip = await ac.post(
        "/api/v1/onboarding/checklist/steps/setup_company/unskip", headers=headers
    )
    assert unskip.status_code == 200, unskip.text
    assert unskip.json()["data"]["progress_pct"] < 80


@pytest.mark.asyncio
async def test_onboarding_checklist_requires_auth(client):
    ac, _seed = client
    res = await ac.get("/api/v1/onboarding/checklist")
    assert res.status_code == 401
