"""Stage 124 X1 — product variants / custom roles CSV export."""

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
async def test_variants_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product_id = seed["p1"].id

    created = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": "Export Var 124", "sku": "P1-EXP124", "size": "S", "selling_price": 11},
    )
    assert created.status_code == 200, created.text

    exported = await ac.get(
        f"/api/v1/products/variants/export?product_id={product_id}&active_only=false",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "product_sku" in header and "is_active" in header
    assert "P1-EXP124" in exported.text or "Export Var 124" in exported.text


@pytest.mark.asyncio
async def test_roles_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "stage124_export",
            "label": "Stage124 Export Role",
            "base_role": "cashier",
            "record_scope": "own",
            "permissions": {
                "dashboard": ["read"],
                "notifications": ["read"],
                "security": ["read"],
            },
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/roles/export?active_only=false", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "slug" in header and "is_active" in header
    assert "stage124_export" in exported.text or "Stage124 Export Role" in exported.text


def test_variant_role_export_ui_and_service_x1():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 124" in inv
    assert "/products/variants/export" in inv
    assert "Export variants CSV" in inv
    roles = (ROOT / "frontend/app/admin/roles/page.tsx").read_text(encoding="utf-8")
    assert "/roles/export" in roles
    assert "Export custom roles CSV" in roles
    svc = (ROOT / "backend/app/variant_role_export.py").read_text(encoding="utf-8")
    assert "export_variants_csv" in svc
    assert "export_custom_roles_csv" in svc
