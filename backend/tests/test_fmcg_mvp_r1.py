"""FMCG module R2 — schemes, routes, delivery, near-expiry, preview."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app.packages import PACKAGEABLE_MODULES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_fmcg_module_registered():
    assert "fmcg" in PACKAGEABLE_MODULES
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "['FMCG', '/fmcg', 'fmcg']" in shell or '["FMCG", "/fmcg", "fmcg"]' in shell
    page = (ROOT / "frontend/app/(dashboard)/fmcg/page.tsx").read_text(encoding="utf-8")
    assert "/fmcg/schemes" in page
    assert "/fmcg/routes" in page


@pytest.mark.asyncio
async def test_fmcg_scheme_route_stop_lifecycle(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]

    scheme = await ac.post(
        "/api/v1/fmcg/schemes",
        headers=admin,
        json={
            "code": f"SC{suffix}",
            "name": f"Scheme {suffix}",
            "scheme_type": "percent",
            "value": 10,
        },
    )
    assert scheme.status_code == 200, scheme.text
    scheme_id = scheme.json()["data"]["id"]
    assert scheme.json()["data"]["code"] == f"SC{suffix}".upper()
    assert scheme.json()["data"]["is_active"] is True

    preview = await ac.post(
        "/api/v1/fmcg/schemes/preview",
        headers=admin,
        json={"line_qty": 10, "line_amount": 100},
    )
    assert preview.status_code == 200, preview.text
    assert any(p["scheme_id"] == scheme_id for p in preview.json()["data"])

    deactivated = await ac.patch(
        f"/api/v1/fmcg/schemes/{scheme_id}",
        headers=admin,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["data"]["is_active"] is False

    route = await ac.post(
        "/api/v1/fmcg/routes",
        headers=admin,
        json={
            "code": f"RT{suffix}",
            "name": f"Route {suffix}",
            "driver_name": "Driver A",
            "vehicle": "Van-1",
        },
    )
    assert route.status_code == 200, route.text
    route_id = route.json()["data"]["id"]

    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Outlet {suffix}", "profile_type": "registered"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    stop = await ac.post(
        f"/api/v1/fmcg/routes/{route_id}/stops",
        headers=admin,
        json={"customer_id": customer_id, "sequence": 1, "visit_day": "mon"},
    )
    assert stop.status_code == 200, stop.text
    stop_id = stop.json()["data"]["id"]
    assert stop.json()["data"]["delivery_status"] == "pending"

    delivered = await ac.patch(
        f"/api/v1/fmcg/stops/{stop_id}/delivery",
        headers=admin,
        json={"delivery_status": "delivered"},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["data"]["delivery_status"] == "delivered"

    perf = await ac.get("/api/v1/fmcg/routes/performance", headers=admin)
    assert perf.status_code == 200, perf.text
    matched = next(r for r in perf.json()["data"] if r["route_id"] == route_id)
    assert matched["delivered"] >= 1

    expiring = await ac.get("/api/v1/fmcg/expiring?days=30", headers=admin)
    assert expiring.status_code == 200, expiring.text
    assert "batches" in expiring.json()["data"]

    summary = await ac.get("/api/v1/fmcg/summary", headers=admin)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["routes_active"] >= 1
    assert "deliveries_completed" in data


@pytest.mark.asyncio
async def test_fmcg_duplicate_scheme_code_blocked(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:6]
    payload = {
        "code": f"DUP{suffix}",
        "name": f"Dup {suffix}",
        "scheme_type": "fixed",
        "value": 5,
    }
    first = await ac.post("/api/v1/fmcg/schemes", headers=admin, json=payload)
    assert first.status_code == 200, first.text
    clash = await ac.post("/api/v1/fmcg/schemes", headers=admin, json=payload)
    assert clash.status_code == 409, clash.text
