"""Dynamic company/tenant/platform sidebar branding — logo APIs and auth."""

from __future__ import annotations

import io

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"


async def _admin_headers(ac, seed) -> dict:
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _company_headers(base: dict, company_id: str) -> dict:
    h = dict(base)
    h["X-Workspace-Kind"] = "company"
    h["X-Company-ID"] = company_id
    return h


@pytest.mark.asyncio
async def test_company_logo_upload_get_delete_and_serialize(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    headers = _company_headers(await _admin_headers(ac, seed), seed["c1"].id)

    got = await ac.get(f"/api/v1/companies/{seed['c1'].id}", headers=headers)
    assert got.status_code == 200, got.text
    co = got.json()["data"]
    assert co["has_logo"] is False
    assert "business_type_label" in co

    up = await ac.post(
        f"/api/v1/companies/{seed['c1'].id}/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["has_logo"] is True
    assert up.json()["data"]["logo_url"]

    media = await ac.get(f"/api/v1/companies/{seed['c1'].id}/logo", headers=headers)
    assert media.status_code == 200
    assert media.content[:8] == b"\x89PNG\r\n\x1a\n"

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["company"]["has_logo"] is True
    assert me.json()["data"].get("tenant_name")
    mem = next(
        mrow
        for mrow in me.json()["data"]["company_memberships"]
        if mrow["company_id"] == seed["c1"].id
    )
    assert mem["has_logo"] is True

    deleted = await ac.delete(f"/api/v1/companies/{seed['c1'].id}/logo", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["has_logo"] is False

    missing = await ac.get(f"/api/v1/companies/{seed['c1'].id}/logo", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_invalid_logo_upload_rejected(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    headers = _company_headers(await _admin_headers(ac, seed), seed["c1"].id)

    bad = await ac.post(
        f"/api/v1/companies/{seed['c1'].id}/logo",
        headers=headers,
        files={"file": ("evil.exe", io.BytesIO(b"MZ\x00\x00not-an-image"), "application/octet-stream")},
    )
    assert bad.status_code in (400, 415, 422)


@pytest.mark.asyncio
async def test_cashier_cannot_modify_company_branding(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers = _company_headers(headers, seed["c1"].id)

    up = await ac.post(
        f"/api/v1/companies/{seed['c1'].id}/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert up.status_code in (401, 403)

    patch = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Hacked Name"},
    )
    assert patch.status_code in (401, 403)


@pytest.mark.asyncio
async def test_company_a_logo_not_accessible_via_company_b(client, tmp_path, monkeypatch, db_session):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")

    ac, seed = client
    admin_a = _company_headers(await _admin_headers(ac, seed), seed["c1"].id)

    up = await ac.post(
        f"/api/v1/companies/{seed['c1'].id}/logo",
        headers=admin_a,
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert up.status_code == 200, up.text

    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="BRAND-B",
        name="Sibling Brand Co",
        industry="bakery",
        is_active=True,
        is_default=False,
    )
    db_session.add(c_b)
    await db_session.flush()
    db_session.add(
        m.UserCompanyMembership(
            tenant_id=seed["t1"].id,
            company_id=c_b.id,
            user_id=seed["u1"].id,
            role="cashier",
            is_active=True,
        )
    )
    await db_session.commit()

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers_b = _company_headers(cashier, c_b.id)
    steal = await ac.post(
        f"/api/v1/companies/{seed['c1'].id}/logo",
        headers=headers_b,
        files={"file": ("other.png", io.BytesIO(_png()), "image/png")},
    )
    assert steal.status_code in (401, 403, 404)

    foreign = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    foreign = _company_headers(foreign, seed["c2"].id)
    leak = await ac.get(f"/api/v1/companies/{seed['c1'].id}/logo", headers=foreign)
    assert leak.status_code in (403, 404)


@pytest.mark.asyncio
async def test_me_and_workspace_branding_fields(client):
    ac, seed = client
    headers = _company_headers(await _admin_headers(ac, seed), seed["c1"].id)

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    data = me.json()["data"]
    assert data.get("tenant_name")
    assert "tenant_has_logo" in data
    assert data.get("company")
    assert "has_logo" in data["company"]
    assert "business_type_label" in data["company"]

    ws = await ac.get("/api/v1/workspace", headers=headers)
    assert ws.status_code == 200, ws.text
    w = ws.json()["data"]
    assert w.get("tenant_name")
    assert "tenant_has_logo" in w
    assert any(c["id"] == seed["c1"].id and "has_logo" in c for c in w.get("companies", []))


@pytest.mark.asyncio
async def test_patch_company_name_for_sidebar(client):
    ac, seed = client
    headers = _company_headers(await _admin_headers(ac, seed), seed["c1"].id)

    r = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Ribdigi Restaurant"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "Ribdigi Restaurant"

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.json()["data"]["company"]["name"] == "Ribdigi Restaurant"


@pytest.mark.asyncio
async def test_tenant_workspace_branding_fields_without_company_logo(client):
    """Tenant workspace exposes tenant branding; company logo is not implied."""
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    data = me.json()["data"]
    assert data.get("workspace_kind") in ("tenant", None) or data.get("tenant_name")
    assert "tenant_has_logo" in data
    assert data.get("tenant_name")
