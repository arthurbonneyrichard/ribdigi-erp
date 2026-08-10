"""Stage 21 C1: Company / currency / tax fidelity (BR-2.1, 2.6, 2.8)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import fx as fx_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_company_currency_tax_fidelity(client, monkeypatch):
    """BR-2.1 / 2.6 / 2.8: company profile, FX, tax rates + category + compound."""
    ac, seed = client
    headers = await _super(ac, seed)

    # --- BR-2.1 company legal / multi-address / contact ---
    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "legal_name": "Alpha Retail Limited",
            "registration_number": "CS123456789",
            "tax_registration_number": "C0009876543",
            "billing_address": "Billing: 1 Independence Ave",
            "shipping_address": "Shipping: Dock 4, Tema",
            "warehouse_address": "Warehouse: Cold Chain Bay 2",
            "contact_person_name": "Ada Contact",
            "contact_person_email": "ada.c1@alpha.example.com",
            "contact_person_phone": "+233203333333",
            "currency": "GHS",
        },
    )
    assert profile.status_code == 200, profile.text
    pdata = profile.json()["data"]
    assert pdata["legal_name"] == "Alpha Retail Limited"
    assert pdata["registration_number"] == "CS123456789"
    assert pdata["tax_registration_number"] == "C0009876543"
    assert pdata["billing_address"] == "Billing: 1 Independence Ave"
    assert pdata["shipping_address"] == "Shipping: Dock 4, Tema"
    assert pdata["warehouse_address"] == "Warehouse: Cold Chain Bay 2"
    assert pdata["contact_person_name"] == "Ada Contact"
    assert pdata["contact_person_email"] == "ada.c1@alpha.example.com"
    assert pdata["contact_person_phone"] == "+233203333333"
    assert pdata["currency"] == "GHS"

    me = await ac.get("/api/v1/tenants/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["registration_number"] == "CS123456789"
    assert me.json()["data"]["billing_address"].startswith("Billing:")

    # --- BR-2.6 currency / FX ---
    upsert = await ac.put(
        "/api/v1/credit/exchange-rates/USD",
        headers=headers,
        json={"currency_code": "USD", "rate_to_base": 12.5},
    )
    assert upsert.status_code == 200, upsert.text
    assert upsert.json()["data"]["currency_code"] == "USD"
    assert float(upsert.json()["data"]["rate_to_base"]) == pytest.approx(12.5)
    assert upsert.json()["data"]["source"] == "manual"

    rates = await ac.get("/api/v1/credit/exchange-rates", headers=headers)
    assert rates.status_code == 200, rates.text
    rdata = rates.json()["data"]
    assert rdata["base_currency"] == "GHS"
    assert any(r["currency_code"] == "USD" for r in rdata["rates"])

    settings_upd = await ac.patch(
        "/api/v1/credit/exchange-rates/settings",
        headers=headers,
        json={"fx_auto_refresh": True},
    )
    assert settings_upd.status_code == 200, settings_upd.text
    assert settings_upd.json()["data"]["fx_auto_refresh"] is True

    async def fake_fetch(base: str):
        assert base == "GHS"
        return "open_er_api", {"USD": 0.08, "EUR": 0.05}

    monkeypatch.setattr(fx_svc, "fetch_provider_rates", fake_fetch)
    refreshed = await ac.post(
        "/api/v1/credit/exchange-rates/refresh",
        headers=headers,
        json={"currencies": ["USD", "EUR"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["provider"] == "open_er_api"
    assert refreshed.json()["data"]["updated_count"] >= 1

    # Transaction-level currency selection on sales invoice
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "currency": "USD",
            "exchange_rate": 12.5,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 10,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    assert inv.json()["data"]["currency"] == "USD"
    assert float(inv.json()["data"]["exchange_rate"]) == pytest.approx(12.5)

    # --- BR-2.8 tax rates / default / category / compound ---
    vat = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "C1 Standard VAT",
            "rate": 15,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": True,
            "is_active": True,
        },
    )
    assert vat.status_code == 200, vat.text
    vat_id = vat.json()["data"]["id"]
    assert vat.json()["data"]["is_default"] is True

    gst = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "C1 GST Split",
            "rate": 18,
            "tax_type": "gst",
            "pricing_mode": "exclusive",
            "is_default": False,
            "components": [
                {"code": "cgst", "name": "CGST", "rate": 9, "basis": "net"},
                {"code": "sgst", "name": "SGST", "rate": 9, "basis": "net"},
            ],
        },
    )
    assert gst.status_code == 200, gst.text
    gst_id = gst.json()["data"]["id"]
    assert gst.json()["data"]["components"]
    assert len(gst.json()["data"]["components"]) == 2

    make_default = await ac.post(f"/api/v1/tax/rates/{vat_id}/default", headers=headers)
    assert make_default.status_code == 200, make_default.text
    assert make_default.json()["data"]["is_default"] is True

    listed = await ac.get("/api/v1/tax/rates", headers=headers)
    assert listed.status_code == 200, listed.text
    by_id = {r["id"]: r for r in listed.json()["data"]}
    assert by_id[vat_id]["is_default"] is True
    assert by_id[gst_id]["tax_type"] == "gst"

    calc = await ac.post(
        "/api/v1/tax/calculate",
        headers=headers,
        json={"amount": 100, "tax_rate_id": gst_id},
    )
    assert calc.status_code == 200, calc.text
    assert float(calc.json()["data"]["tax"]) == pytest.approx(18.0)

    cat = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={
            "code": "C1TAX",
            "name": "C1 Taxable Goods",
            "tax_rate_id": gst_id,
        },
    )
    assert cat.status_code == 200, cat.text
    assert cat.json()["data"]["tax_rate_id"] == gst_id


def test_br_2_1_2_6_2_8_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")

    s21 = br.split("#### BR-2.1 Company Information")[1].split("#### BR-2.2")[0]
    assert "[x] CRUD operations on company legal name, registration number, tax ID" in s21
    assert "[x] Multiple address support" in s21
    assert "[x] Contact person designation" in s21
    assert "Stage 21 C1" in s21
    assert "test_company_currency_tax_c1.py" in s21

    s26 = br.split("#### BR-2.6 Currency Setup")[1].split("#### BR-2.7")[0]
    assert "[x] Add currencies with exchange rates" in s26
    assert "[x] Set base currency" in s26
    assert "[x] Auto-update exchange rates" in s26
    assert "[x] Transaction-level currency selection" in s26
    assert "Stage 21 C1" in s26

    s27 = br.split("#### BR-2.7 Language Configuration")[1].split("#### BR-2.8")[0]
    assert "ADR-006" in s27 or "[ ]" in s27  # packs remain deferred

    s28 = br.split("#### BR-2.8 Tax Configuration")[1].split("---")[0]
    assert "[x] Add multiple tax rates" in s28
    assert "[x] Set default tax rate" in s28
    assert "[x] Tax applicability by product category" in s28
    assert "[x] Compound tax support" in s28
    assert "Stage 21 C1" in s28

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    c1_line = [ln for ln in plan.splitlines() if "| **C1**" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_company_currency_tax_c1.py" in plan
