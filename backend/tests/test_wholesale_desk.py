"""Wholesale is a business type again (13 Nov 2026): the retail desk with the wholesale channel."""

from __future__ import annotations

import pytest

from app import desks, hrm, industry_dashboard, packages, trade
from app.tenants import PROVISION_INDUSTRIES, VALID_INDUSTRIES, normalize_industry
from tests.conftest import auth_headers, set_tenant_industry


def test_wholesale_runs_on_the_retail_desk():
    assert "wholesale" in VALID_INDUSTRIES and "wholesale" in PROVISION_INDUSTRIES
    assert normalize_industry("Wholesaler") == "wholesale"
    assert packages.canonicalize_industry("wholesale") == "wholesale"
    assert desks.desk_for_industry("wholesale") == "retail"
    assert industry_dashboard.dashboard_layout("wholesale") == "retail"
    assert "wholesale" in industry_dashboard.POS_INDUSTRIES
    assert trade.default_sales_channel("wholesale", source="pos") == "wholesale"
    assert trade.default_sales_channel("wholesale", source="order") == "wholesale"
    assert packages.industry_allows_module("wholesale", "hrm")
    assert not packages.industry_allows_module("wholesale", "hotel")
    assert hrm.hr_areas_for("wholesale") == hrm.hr_areas_for("retail")


@pytest.mark.asyncio
async def test_wholesale_company_signs_in_with_hr_and_quotes(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = (await ac.get("/api/v1/me", headers=h)).json()["data"]
    assert me.get("industry") == "wholesale"
    assert (await ac.get("/api/v1/hrm/summary", headers=h)).status_code == 200
    assert (await ac.get("/api/v1/hotel/rooms", headers=h)).status_code in (403, 404)
