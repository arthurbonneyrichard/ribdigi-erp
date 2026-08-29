"""StoreDrawerSettingsUpdate.drawer_host OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StoreDrawerSettingsUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cash_drawer_host_schema():
    omit = StoreDrawerSettingsUpdate.model_validate({})
    assert omit.drawer_host is None
    ok = StoreDrawerSettingsUpdate.model_validate(
        {"drawer_host": "  Printer.Local  ", "drawer_mode": "network"}
    )
    assert ok.drawer_host == "printer.local"
    ip = StoreDrawerSettingsUpdate.model_validate({"drawer_host": "127.0.0.1"})
    assert ip.drawer_host == "127.0.0.1"
    for bad in (
        "",
        " ",
        "not a host",
        "http://127.0.0.1",
        "user@printer.local",
        "...",
    ):
        with pytest.raises(ValidationError):
            StoreDrawerSettingsUpdate.model_validate({"drawer_host": bad})


def test_cash_drawer_host_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash drawer host"' in page
    assert "drawerHost.trim() || null" in page
    assert 'aria-label="Save drawer settings"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Cash drawer host OpenAPI" in agents
    assert "SmtpHostValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Cash drawer host" in docs
    assert "SmtpHostValue" in docs


@pytest.mark.asyncio
async def test_cash_drawer_host_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    tenant = seed["t1"]
    tenant.max_stores_override = 50
    tenant.store_limit = 50
    await db_session.commit()

    store = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "DRW1", "name": "Drawer Host Tip Store"},
    )
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]

    blank = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_host": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_host": "not a host"},
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_host": "http://127.0.0.1"},
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={
            "drawer_mode": "network",
            "drawer_host": "127.0.0.1",
            "drawer_port": 9100,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["drawer_host"] == "127.0.0.1"
    assert ok.json()["data"]["drawer_mode"] == "network"

    # blank host with network mode still fails service required-host check when null
    missing = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_mode": "network", "drawer_host": None},
    )
    assert missing.status_code == 400, missing.text

    # restore mock so store stays usable
    restore = await ac.patch(
        f"/api/v1/stores/{store_id}/drawer",
        headers=admin,
        json={"drawer_mode": "mock", "drawer_host": None},
    )
    assert restore.status_code == 200, restore.text
