"""Stage 122 X1 — branches / departments / catalog-meta CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_branches_and_departments_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    br = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "EXP122B", "name": "Export Branch 122"},
    )
    assert br.status_code == 200, br.text

    dep = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "EXP122D", "name": "Export Dept 122"},
    )
    assert dep.status_code == 200, dep.text

    bex = await ac.get("/api/v1/branches/export", headers=headers)
    assert bex.status_code == 200, bex.text
    assert "text/csv" in bex.headers.get("content-type", "")
    assert "EXP122B" in bex.text or "Export Branch 122" in bex.text

    dex = await ac.get("/api/v1/departments/export", headers=headers)
    assert dex.status_code == 200, dex.text
    assert "head_user_id" in dex.text.splitlines()[0]
    assert "EXP122D" in dex.text or "Export Dept 122" in dex.text


@pytest.mark.asyncio
async def test_catalog_meta_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "EXP122C", "name": "Export Cat 122"},
    )
    assert cat.status_code == 200, cat.text
    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "EXP122BR", "name": "Export Brand 122"},
    )
    assert brand.status_code == 200, brand.text
    unit = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "EXP122U", "name": "Export Unit 122"},
    )
    assert unit.status_code == 200, unit.text

    for path, token in (
        ("/api/v1/catalog/categories/export", "EXP122C"),
        ("/api/v1/catalog/brands/export", "EXP122BR"),
        ("/api/v1/catalog/units/export", "EXP122U"),
    ):
        exported = await ac.get(path, headers=headers)
        assert exported.status_code == 200, exported.text
        assert "text/csv" in exported.headers.get("content-type", "")
        assert token in exported.text


def test_org_catalog_export_ui_and_service_x1():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 122" in company
    assert "/branches/export" in company
    assert "Export branches CSV" in company
    assert "/departments/export" in company
    assert "Export departments CSV" in company
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "/catalog/categories/export" in inv
    assert "Export categories CSV" in inv
    assert "/catalog/brands/export" in inv
    assert "Export brands CSV" in inv
    assert "/catalog/units/export" in inv
    assert "Export units CSV" in inv
    svc = (ROOT / "backend/app/org_catalog_export.py").read_text(encoding="utf-8")
    assert "export_branches_csv" in svc
    assert "export_departments_csv" in svc
    assert "export_categories_csv" in svc
    assert "export_brands_csv" in svc
    assert "export_units_csv" in svc
