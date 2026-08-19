"""Stage 119 E1 — customers/suppliers CSV export."""

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
async def test_customers_and_suppliers_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Export Customer Co", "party_type": "registered", "code": "CUST-EXP"},
    )
    assert cust.status_code == 200, cust.text

    sup = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Export Supplier Co", "code": "SUP-EXP"},
    )
    assert sup.status_code == 200, sup.text

    cust_csv = await ac.get("/api/v1/customers/export", headers=headers)
    assert cust_csv.status_code == 200, cust_csv.text
    assert "text/csv" in cust_csv.headers.get("content-type", "")
    assert "Export Customer Co" in cust_csv.text
    assert "CUST-EXP" in cust_csv.text
    assert "name,code" in cust_csv.text.splitlines()[0]

    sup_csv = await ac.get("/api/v1/suppliers/export", headers=headers)
    assert sup_csv.status_code == 200, sup_csv.text
    assert "text/csv" in sup_csv.headers.get("content-type", "")
    assert "Export Supplier Co" in sup_csv.text
    assert "SUP-EXP" in sup_csv.text
    assert "name,code" in sup_csv.text.splitlines()[0]


def test_sales_purchasing_export_buttons_e1():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 119" in sales
    assert "/customers/export" in sales
    assert "Export customers CSV" in sales
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "/suppliers/export" in purchasing
    assert "Export suppliers CSV" in purchasing
    svc = (ROOT / "backend/app/party_export.py").read_text(encoding="utf-8")
    assert "export_customers_csv" in svc
    assert "export_suppliers_csv" in svc
