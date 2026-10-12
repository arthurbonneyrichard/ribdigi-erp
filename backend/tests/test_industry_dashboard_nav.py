"""Industry dashboard cards and nav — tenant.industry from the server, not the client.

Pharmacy extras (lots/batches/Rx catalog/prescriptions) stay off mart/retail.
Hotel home remains /hotel. No hospital HIS or PMS modules are invented.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app import models as m
from app.industry_dashboard import (
    dashboard_layout,
    industry_dashboard_features,
    industry_dashboard_payload,
    industry_home_path,
    shows_retail_operations,
)
from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2]


def test_industry_home_and_feature_catalog():
    assert industry_home_path("hotel") == "/hotel"
    assert industry_home_path("hospitality") == "/hotel"
    assert industry_home_path("pharmacy") == "/dashboard"
    assert industry_home_path("mart") == "/dashboard"
    assert industry_home_path("restaurant") == "/restaurant"
    assert industry_home_path("retail") == "/dashboard"

    for removed in ("pharmacy", "wholesale", "retail_wholesale", "fmcg", "hospital", "mart"):
        assert industry_dashboard_features(removed) == []
        assert industry_home_path(removed) == "/dashboard"
        assert dashboard_layout(removed) == "unconfigured"
        assert shows_retail_operations(removed) is False

    retail = industry_dashboard_features("retail")
    assert retail == []

    restaurant = industry_dashboard_features("restaurant")
    assert {row["id"] for row in restaurant} == {"restaurant_home", "restaurant_orders", "restaurant_kitchen", "printers"}
    assert any(row["href"] == "/restaurant" for row in restaurant)
    assert all(not row["href"].startswith("/hotel") for row in restaurant)

    hotel = industry_dashboard_features("hotel")
    assert any(row["href"] == "/hotel" for row in hotel)


def test_payload_uses_tenant_industry_not_client():
    class T:
        industry = "pharmacy"
        package_code = "professional"
        enabled_modules = None

    payload = industry_dashboard_payload(T())
    assert payload["industry"] is None
    assert payload["dashboard_layout"] == "unconfigured"
    assert payload["show_retail_operations"] is False
    assert payload["industry_features"] == []

    T.industry = "hotel"
    hotel = industry_dashboard_payload(T())
    assert hotel["industry"] == "hotel"
    assert hotel["industry_home"] == "/hotel"
    assert any(row["href"].startswith("/hotel") for row in hotel["industry_features"])

    T.industry = "mart"
    mart = industry_dashboard_payload(T())
    assert mart["industry"] is None
    assert mart["industry_features"] == []
    assert mart["dashboard_layout"] == "unconfigured"

    T.industry = "wholesale"
    wholesale = industry_dashboard_payload(T())
    assert wholesale["industry"] is None
    assert wholesale["industry_features"] == []
    assert wholesale["show_retail_operations"] is False


async def test_dashboard_industry_from_tenant_ignores_query(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["industry"] is None
    assert me.json()["data"]["industry_raw"] == "pharmacy"

    spoofed = await ac.get("/api/v1/dashboard?industry=hotel", headers=admin)
    assert spoofed.status_code == 200, spoofed.text
    data = spoofed.json()["data"]
    assert data["industry"] is None
    assert data["dashboard_layout"] == "unconfigured"
    assert data["show_retail_operations"] is False
    assert data["industry_home"] == "/dashboard"
    assert data["industry_features"] == []

    cashier_dash = await ac.get("/api/v1/dashboard", headers=cashier)
    assert cashier_dash.status_code == 200, cashier_dash.text
    assert cashier_dash.json()["data"]["industry"] is None
    assert cashier_dash.json()["data"]["industry_features"] == []
    assert cashier_dash.json()["data"]["show_retail_operations"] is False


async def test_mart_dashboard_omits_pharmacy_tiles(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "mart")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    data = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert data["industry"] is None
    assert data["dashboard_layout"] == "unconfigured"
    assert data["show_retail_operations"] is False
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
    assert data["industry_home"] == "/restaurant"
    hrefs = [row["href"] for row in data["industry_features"]]
    assert "/pos" not in hrefs
    assert "/restaurant" in hrefs
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
    assert data["industry"] is None
    assert data["dashboard_layout"] == "unconfigured"
    assert data["show_retail_operations"] is False
    hrefs = [row["href"] for row in data["industry_features"]]
    assert "/fmcg" not in hrefs
    assert all(not href.startswith("/hotel") for href in hrefs)


def test_frontend_industry_dashboard_and_nav_source():
    dash = (ROOT / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(encoding="utf-8")
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    helper = (ROOT / "frontend/lib/industryDashboard.ts").read_text(encoding="utf-8")
    backend = (ROOT / "backend/app/industry_dashboard.py").read_text(encoding="utf-8")

    assert "industryHomePath" in dash
    assert "router.replace(home)" in dash
    assert "industry_features" in dash
    assert "return 'Pharmacy'" not in helper
    assert "id: 'batches'" in helper or 'id: "batches"' in helper
    assert "tab=batches" in helper
    assert "tab=expiry" in helper
    assert "/prescriptions" in helper
    assert "PHARMACY_NAV_ITEMS" not in nav
    assert "label: 'Pharmacy'" not in nav
    assert "'/pharmacy'" not in nav and '"/pharmacy"' not in nav
    assert "HIS" in backend or "dispensing" in backend.lower()
    hotel_block = nav[nav.find("export const HOTEL_NAV_ITEMS") : nav.find("export const FMCG_NAV_ITEMS")]
    assert "Pharmacy" not in hotel_block
    assert "['POS'" not in hotel_block


def test_software_owner_dashboard_is_platform_home_not_an_operating_desk():
    assert dashboard_layout("software") == "platform"
    assert industry_home_path("software") == "/platform"
    assert shows_retail_operations("software") is False
    assert industry_dashboard_features("software") == []
    payload = industry_dashboard_payload(SimpleNamespace(industry="software"))
    assert payload == {
        "industry": "software",
        "industry_home": "/platform",
        "industry_features": [],
        "dashboard_layout": "platform",
        "show_retail_operations": False,
    }
    assert "pharmacy_desk" not in payload
    assert dashboard_layout("retail") == "retail"
    assert dashboard_layout("pharmacy") == "unconfigured"
    assert shows_retail_operations("retail") is True
    assert shows_retail_operations("pharmacy") is False
    assert industry_home_path("pharmacy") == "/dashboard"
    assert industry_home_path("hotel") == "/hotel"
    assert industry_home_path("restaurant") == "/restaurant"


async def test_software_dashboard_is_not_a_customer_operating_desk(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "software")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    body = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert body["dashboard_layout"] == "platform"
    assert body["industry"] == "software"
    assert body["industry_home"] == "/platform"
    assert body["industry_features"] == []
    assert body["show_retail_operations"] is False
    assert body["pharmacy_desk"] is None
    assert body["fmcg_desk"] is None
    assert body["hospital_desk"] is None
    assert body["wholesale_desk"] is None
    assert body["recent_sales"] == []
    assert "total_sales" not in body
    assert "sales" not in body["links"]
    assert "pos" not in body["links"]
    assert body["links"]["platform"] == "/platform"
    assert body["links"]["support"] == "/platform/support"
    await set_tenant_industry(db_session, seed["t1"], "retail")
    overview = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    assert "Open support tickets" in overview
    assert "Companies" in overview
    assert "Subscriptions" in overview
    assert "No open support tickets." in overview
    assert "Total Sales" not in overview
    assert "Pharmacy" not in overview
    assert "Front desk" not in overview
    assert "Kitchen" not in overview


def test_dashboard_layout_does_not_treat_other_industries_as_retail():
    assert dashboard_layout("retail") == "retail"
    assert shows_retail_operations("retail") is True
    assert dashboard_layout("pharmacy") == "unconfigured"
    assert shows_retail_operations("pharmacy") is False
    assert dashboard_layout("fmcg") == "unconfigured"
    assert dashboard_layout("hospital") == "unconfigured"
    assert dashboard_layout("wholesale") == "unconfigured"
    assert dashboard_layout("retail_wholesale") == "unconfigured"
    assert shows_retail_operations("retail_wholesale") is False
    assert dashboard_layout("mart") == "unconfigured"
    assert dashboard_layout("bakery") == "unconfigured"
    assert dashboard_layout(None) == "unconfigured"
    assert dashboard_layout("not-an-industry") == "unconfigured"
    assert shows_retail_operations(None) is False
    assert shows_retail_operations("mart") is False


async def test_industry_desks_and_route_gates(client, db_session):
    ac, seed = client
    db_session.add(m.HospitalPatient(tenant_id=seed["t2"].id, name="Beta Patient"))
    db_session.add(m.FmcgTradeScheme(tenant_id=seed["t2"].id, code="BETA1", name="Beta scheme"))
    await db_session.commit()

    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    pharmacy = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert pharmacy["dashboard_layout"] == "unconfigured"
    assert pharmacy["show_retail_operations"] is False
    assert pharmacy["pharmacy_desk"] is None
    assert pharmacy["fmcg_desk"] is None
    assert pharmacy["hospital_desk"] is None
    assert pharmacy["industry_features"] == []

    gift = await ac.post("/api/v1/gift-cards", headers=admin, json={"amount": 10})
    assert gift.status_code == 403, gift.text
    assert gift.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"
    pharmacy_pos = await ac.get("/api/v1/pos/sessions", headers=admin)
    assert pharmacy_pos.status_code == 403, pharmacy_pos.text
    assert pharmacy_pos.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "retail")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    retail = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert retail["dashboard_layout"] == "retail"
    assert retail["show_retail_operations"] is True
    assert retail["pharmacy_desk"] is None

    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    fmcg = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert fmcg["dashboard_layout"] == "unconfigured"
    assert fmcg["show_retail_operations"] is False
    assert fmcg["fmcg_desk"] is None
    assert "/fmcg" not in [row["href"] for row in fmcg["industry_features"]]
    denied_pos = await ac.get("/api/v1/pos/sessions", headers=admin)
    assert denied_pos.status_code == 403, denied_pos.text
    assert denied_pos.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "hospital")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    hospital = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert hospital["dashboard_layout"] == "unconfigured"
    assert hospital["show_retail_operations"] is False
    assert hospital["hospital_desk"] is None
    assert all(row["href"] != "/hospital" for row in hospital["industry_features"])
    denied_fmcg = await ac.get("/api/v1/fmcg/summary", headers=admin)
    assert denied_fmcg.status_code == 403, denied_fmcg.text
    denied_rx = await ac.get("/api/v1/pharmacy/prescriptions", headers=admin)
    assert denied_rx.status_code == 403, denied_rx.text

    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    wholesale = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert wholesale["dashboard_layout"] == "unconfigured"
    assert wholesale["show_retail_operations"] is False
    assert wholesale["wholesale_desk"] is None
    denied_wholesale_pos = await ac.get("/api/v1/pos/sessions", headers=admin)
    assert denied_wholesale_pos.status_code == 403, denied_wholesale_pos.text

    await set_tenant_industry(db_session, seed["t1"], "not-an-industry")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    missing = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert missing["dashboard_layout"] == "unconfigured"
    assert missing["show_retail_operations"] is False
    assert missing["industry_features"] == []


async def test_non_retail_never_gets_retail_operations_or_other_tenant_rows(client, db_session):
    ac, seed = client
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_dash = (await ac.get("/api/v1/dashboard", headers=beta)).json()["data"]
    assert beta_dash["products"] == 1

    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    pharmacy = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert pharmacy["dashboard_layout"] == "unconfigured"
    assert pharmacy["show_retail_operations"] is False
    assert pharmacy["products"] == 1
    assert pharmacy["industry"] is None

    same_token = await ac.get("/api/v1/dashboard", headers=admin)
    assert same_token.json()["data"]["industry"] is None
    assert same_token.json()["data"]["products"] == 1

    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    switched = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert switched["industry"] is None
    assert switched["dashboard_layout"] == "unconfigured"
    assert switched["show_retail_operations"] is False
    assert switched["industry_features"] == []
    assert switched["products"] == 1

    pos = await ac.post("/api/v1/pos/sessions/open", headers=admin, json={"opening_cash": 0})
    assert pos.status_code == 403, pos.text
    assert pos.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/fmcg/summary", headers=cashier)
    assert denied.status_code == 403, denied.text

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    fmcg = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert fmcg["dashboard_layout"] == "unconfigured"
    assert fmcg["show_retail_operations"] is False
    assert fmcg["products"] == 1

    await set_tenant_industry(db_session, seed["t1"], "retail_wholesale")
    combo = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert combo["dashboard_layout"] == "unconfigured"
    assert combo["show_retail_operations"] is False
    assert combo["products"] == 1
    assert combo["wholesale_desk"] is None

    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    restaurant = (await ac.get("/api/v1/dashboard", headers=admin)).json()["data"]
    assert restaurant["dashboard_layout"] == "restaurant"
    assert restaurant["show_retail_operations"] is False
    assert restaurant["industry_home"] == "/restaurant"
