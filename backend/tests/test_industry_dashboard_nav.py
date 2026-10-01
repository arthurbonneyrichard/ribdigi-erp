"""Industry dashboard cards and nav — tenant.industry from the server, not the client.

Pharmacy extras (lots/batches/Rx catalog/prescriptions) stay off mart/retail.
Hotel home remains /hotel. No hospital HIS or PMS modules are invented.
"""

from __future__ import annotations

from pathlib import Path

from app.industry_dashboard import (
    industry_dashboard_features,
    industry_dashboard_payload,
    industry_home_path,
)
from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2]


def test_industry_home_and_feature_catalog():
    assert industry_home_path("hotel") == "/hotel"
    assert industry_home_path("hospitality") == "/hotel"
    assert industry_home_path("pharmacy") == "/dashboard"
    assert industry_home_path("mart") == "/dashboard"
    assert industry_home_path("restaurant") == "/dashboard"
    assert industry_home_path("retail") == "/dashboard"

    pharmacy_ids = {row["id"] for row in industry_dashboard_features("pharmacy")}
    assert pharmacy_ids == {"expiry_lots", "batches", "pos", "rx_products", "prescriptions"}
    assert all(not row["href"].startswith("/hotel") for row in industry_dashboard_features("pharmacy"))
    assert any(row["href"] == "/prescriptions" for row in industry_dashboard_features("pharmacy"))

    mart = industry_dashboard_features("mart")
    assert mart == []
    retail = industry_dashboard_features("retail")
    assert {row["id"] for row in retail} == {"pos", "inventory", "customers"}
    wholesale = industry_dashboard_features("wholesale")
    assert "quotes" in {row["id"] for row in wholesale}
    combo = industry_dashboard_features("retail_wholesale")
    assert {row["id"] for row in combo} >= {"pos", "quotes", "orders"}
    assert "batches" not in {row["id"] for row in mart}

    restaurant = industry_dashboard_features("restaurant")
    assert {row["id"] for row in restaurant} == {"pos", "printers"}
    assert all(not row["href"].startswith("/hotel") for row in restaurant)

    hotel = industry_dashboard_features("hotel")
    assert any(row["href"] == "/hotel" for row in hotel)


def test_payload_uses_tenant_industry_not_client():
    class T:
        industry = "pharmacy"
        package_code = "professional"
        enabled_modules = None

    payload = industry_dashboard_payload(T())
    assert payload["industry"] == "pharmacy"
    assert {row["id"] for row in payload["industry_features"]} == {
        "expiry_lots",
        "batches",
        "pos",
        "rx_products",
        "prescriptions",
    }

    T.industry = "hotel"
    hotel = industry_dashboard_payload(T())
    assert hotel["industry"] == "hotel"
    assert hotel["industry_home"] == "/hotel"
    assert any(row["href"].startswith("/hotel") for row in hotel["industry_features"])

    T.industry = "mart"
    mart = industry_dashboard_payload(T())
    assert mart["industry_features"] == []

    T.industry = "wholesale"
    wholesale = industry_dashboard_payload(T())
    assert {row["id"] for row in wholesale["industry_features"]} >= {"quotes", "orders", "credit"}


async def test_dashboard_industry_from_tenant_ignores_query(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["industry"] == "pharmacy"

    spoofed = await ac.get("/api/v1/dashboard?industry=hotel", headers=admin)
    assert spoofed.status_code == 200, spoofed.text
    data = spoofed.json()["data"]
    assert data["industry"] == "pharmacy"
    assert data["industry_home"] == "/dashboard"
    ids = {row["id"] for row in data["industry_features"]}
    assert "batches" in ids
    assert "expiry_lots" in ids
    assert all(not str(row.get("href") or "").startswith("/hotel") for row in data["industry_features"])

    cashier_dash = await ac.get("/api/v1/dashboard", headers=cashier)
    assert cashier_dash.status_code == 200, cashier_dash.text
    assert cashier_dash.json()["data"]["industry"] == "pharmacy"
    assert {row["id"] for row in cashier_dash.json()["data"]["industry_features"]} >= {
        "batches",
        "expiry_lots",
        "pos",
    }


async def test_mart_dashboard_omits_pharmacy_tiles(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "mart")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    data = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert data["industry"] == "mart"
    assert data["industry_home"] == "/dashboard"
    ids = {row["id"] for row in data["industry_features"]}
    assert "batches" not in ids
    assert "expiry_lots" not in ids
    assert data["links"]["low_stock"] == "/inventory?tab=lowstock"
    assert data["links"]["out_of_stock"] == "/inventory?tab=products&stock=oos"
    assert data["links"]["expiring"] == "/inventory?tab=expiry"


async def test_restaurant_dashboard_omits_hotel_pms(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    data = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert data["industry"] == "restaurant"
    assert data["industry_home"] == "/dashboard"
    hrefs = [row["href"] for row in data["industry_features"]]
    assert "/pos" in hrefs
    assert "/printers" in hrefs
    assert all(not href.startswith("/hotel") for href in hrefs)
    denied = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert denied.status_code == 403, denied.text


async def test_hotel_dashboard_home_stays_hotel(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    data = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert data["industry"] == "hotel"
    assert data["industry_home"] == "/hotel"
    assert any(row["href"] == "/hotel" for row in data["industry_features"])


async def test_fmcg_dashboard_features_not_hotel(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    data = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert data["industry"] == "fmcg"
    hrefs = [row["href"] for row in data["industry_features"]]
    assert "/fmcg" in hrefs
    assert all(not href.startswith("/hotel") for href in hrefs)


def test_frontend_industry_dashboard_and_nav_source():
    dash = (ROOT / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    helper = (ROOT / "frontend/lib/industryDashboard.ts").read_text(encoding="utf-8")
    backend = (ROOT / "backend/app/industry_dashboard.py").read_text(encoding="utf-8")

    assert "industryHomePath" in dash
    assert "router.replace('/hotel')" in dash
    assert "industry_features" in dash
    assert "Pharmacy management" in helper
    assert "id: 'batches'" in helper or 'id: "batches"' in helper
    assert "tab=batches" in helper
    assert "tab=expiry" in helper
    assert "/prescriptions" in helper
    assert "PHARMACY_NAV_ITEMS" in nav
    assert "label: 'Pharmacy management'" in nav
    assert "HIS" in backend or "dispensing" in backend.lower()
    hotel_block = nav[nav.find("export const HOTEL_NAV_ITEMS") : nav.find("export const FMCG_NAV_ITEMS")]
    assert "Pharmacy" not in hotel_block
    assert "['POS'" not in hotel_block
