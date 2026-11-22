"""FMCG report exports (Excel, PDF) and report filters."""

from __future__ import annotations

import io
import re
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from app import fmcg_exports
from app import fmcg_reports
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
R = f"{API}/reports/run"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _sell(ac, h, db_session, seed, name, price=100, cost=60, qty=10, route_id=None, category_id=None, rep=None):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"E{uuid4().hex[:7]}", cost_price=cost, selling_price=price,
                  stock_qty=500, is_active=True, tracks_batches=False, category_id=category_id)
    db_session.add(p)
    await db_session.commit()
    body = {"name": f"Kiosk {uuid4().hex[:4]}"}
    if route_id:
        body["route_id"] = route_id
    if rep:
        body["salesperson_name"] = rep
    outlet = (await ac.post(f"{API}/outlets", headers=h, json=body)).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": qty}]})).json()["data"]
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    return p, outlet


def _sample(rows=3):
    return {
        "title": "Test report", "period": {"start": "2026-11-01", "end": "2026-11-20"}, "filters_text": "product = Soap", "note": "A note",
        "columns": [{"key": "name", "label": "Name", "kind": "text"}, {"key": "sales", "label": "Sales", "kind": "money"}, {"key": "units", "label": "Units", "kind": "number"}],
        "rows": [{"name": f"Item {i}", "sales": 1234.5 * i, "units": i} for i in range(rows)], "row_count": rows, "truncated": False,
    }


def test_xlsx_is_a_real_workbook_with_formats_and_no_formulas():
    rep = _sample()
    rep["rows"][0]["name"] = "=HYPERLINK(\"http://evil\",\"x\")"
    rep["rows"][1]["name"] = "+cmd|' /C calc'!A0"
    wb = load_workbook(io.BytesIO(fmcg_exports.to_xlsx(rep)))
    ws = wb.active
    assert ws.title == "Test report" and ws["A1"].value == "Test report" and ws["A1"].font.bold
    rows = list(ws.iter_rows(values_only=False))
    header = next(r for r in rows if r[0].value == "Name")
    assert [c.value for c in header] == ["Name", "Sales", "Units"] and header[0].font.bold
    first = rows[rows.index(header) + 1]
    assert first[0].data_type == "s" and first[0].value.startswith("=")  # stored as text, never a formula
    second = rows[rows.index(header) + 2]
    assert second[0].data_type == "s"
    assert second[1].value == 1234.5 and second[1].number_format == "#,##0.00"
    assert ws.freeze_panes is not None


def test_pdf_is_valid_paginates_and_keeps_columns_aligned():
    small = fmcg_exports.to_pdf(_sample(3))
    assert small.startswith(b"%PDF-1.4") and small.rstrip().endswith(b"%%EOF") and b"/Count 1" in small
    assert b"Test report" in small and b"Page 1 of 1" in small
    big = fmcg_exports.to_pdf(_sample(300))
    count = int(re.search(rb"/Count (\d+)", big).group(1))
    assert count >= 5 and f"Page {count} of {count}".encode() in big
    assert big.count(b"Name") >= count  # the header repeats on every page
    # Every object offset in the cross-reference table points at "N 0 obj".
    xref = int(re.search(rb"startxref\n(\d+)", big).group(1))
    table = big[xref:].split(b"\n")
    n = int(table[1].split()[1])
    for i in range(1, n):
        off = int(table[2 + i].split()[0])
        assert big[off:].startswith(f"{i} 0 obj".encode())
    wide = _sample(2)
    wide["columns"] = [{"key": f"c{i}", "label": f"Column number {i}", "kind": "text"} for i in range(14)]
    wide["rows"] = [{f"c{i}": "x" * 60 for i in range(14)}]
    assert fmcg_exports.to_pdf(wide).startswith(b"%PDF")
    empty = _sample(0)
    assert b"Nothing to show" in fmcg_exports.to_pdf(empty)
    odd = _sample(1)
    odd["rows"][0]["name"] = "Café (Ghana) \\ €"
    assert fmcg_exports.to_pdf(odd).startswith(b"%PDF")


@pytest.mark.asyncio
async def test_every_report_downloads_as_excel_and_pdf(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _sell(ac, h, db_session, seed, "Soap")
    for entry in fmcg_reports.CATALOGUE:
        x = await ac.get(f"{R}?report={entry['id']}&format=xlsx", headers=h)
        assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats"), entry["id"]
        assert load_workbook(io.BytesIO(x.content)).active is not None
        assert ".xlsx" in x.headers["content-disposition"]
        p = await ac.get(f"{R}?report={entry['id']}&format=pdf", headers=h)
        assert p.status_code == 200 and p.content.startswith(b"%PDF") and p.headers["content-type"] == "application/pdf", entry["id"]
    assert (await ac.get(f"{R}?report=sales_by_product&format=docx", headers=h)).status_code == 422


@pytest.mark.asyncio
async def test_sales_filters_narrow_the_figures(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    cat = m.ProductCategory(tenant_id=seed["t1"].id, name="Drinks", code=f"D{uuid4().hex[:4]}")
    db_session.add(cat)
    await db_session.commit()
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:4]}", "name": "East"})).json()["data"]
    a, oa = await _sell(ac, h, db_session, seed, "Cola", qty=10, route_id=route["id"], category_id=cat.id, rep="Kofi")
    b, ob = await _sell(ac, h, db_session, seed, "Rice", qty=5, rep="Ama")
    allrows = (await ac.get(f"{R}?report=sales_by_product", headers=h)).json()["data"]["rows"]
    assert {r["name"] for r in allrows} >= {a.name, b.name}
    one = (await ac.get(f"{R}?report=sales_by_product&product_id={a.id}", headers=h)).json()["data"]
    assert [r["name"] for r in one["rows"]] == [a.name] and f"product = {a.name}" in one["filters_text"]
    assert [r["name"] for r in (await ac.get(f"{R}?report=sales_by_product&category_id={cat.id}", headers=h)).json()["data"]["rows"]] == [a.name]
    assert [r["name"] for r in (await ac.get(f"{R}?report=sales_by_product&route_id={route['id']}", headers=h)).json()["data"]["rows"]] == [a.name]
    assert [r["name"] for r in (await ac.get(f"{R}?report=sales_by_product&outlet_id={ob}", headers=h)).json()["data"]["rows"]] == [b.name]
    assert [r["name"] for r in (await ac.get(f"{R}?report=sales_by_product&rep=kofi", headers=h)).json()["data"]["rows"]] == [a.name]
    terr = (await ac.post(f"{API}/territories", headers=h, json={"code": f"T{uuid4().hex[:4]}", "name": "Zone", "route_ids": [route["id"]], "rep_user_ids": []})).json()["data"]
    assert [r["name"] for r in (await ac.get(f"{R}?report=sales_by_product&territory_id={terr['id']}", headers=h)).json()["data"]["rows"]] == [a.name]
    both = (await ac.get(f"{R}?report=sales_by_rep&product_id={a.id}&route_id={route['id']}", headers=h)).json()["data"]
    assert [r["name"] for r in both["rows"]] == ["Kofi"]
    none = (await ac.get(f"{R}?report=sales_by_product&product_id={a.id}&outlet_id={ob}", headers=h)).json()["data"]
    assert none["rows"] == []
    csv = (await ac.get(f"{R}?report=sales_by_product&product_id={a.id}&format=csv", headers=h)).text
    assert "Filters: product = " in csv


@pytest.mark.asyncio
async def test_other_report_filters_and_honest_rejection(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, oa = await _sell(ac, h, db_session, seed, "Cola")
    b, ob = await _sell(ac, h, db_session, seed, "Rice")
    v = (await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 5-26", "name": "Van"})).json()["data"]
    fleet = (await ac.get(f"{R}?report=fleet_costs&vehicle_id={v['id']}", headers=h)).json()["data"]
    assert [r["plate"] for r in fleet["rows"]] == ["GR 5-26"]
    stock = (await ac.get(f"{R}?report=stock_valuation&product_id={a.id}", headers=h)).json()["data"]
    assert [r["product"] for r in stock["rows"]] == [a.name]
    assert len((await ac.get(f"{R}?report=receivables_aging&outlet_id={oa}", headers=h)).json()["data"]["rows"]) == 1
    assert (await ac.get(f"{R}?report=receivables_aging&outlet_id={str(uuid4())}", headers=h)).json()["data"]["rows"] == []
    await ac.post(f"{API}/complaints", headers=h, json={"category": "other", "description": "Late delivery", "customer_id": oa})
    assert len((await ac.get(f"{R}?report=complaints&outlet_id={oa}", headers=h)).json()["data"]["rows"]) == 1
    assert (await ac.get(f"{R}?report=complaints&outlet_id={ob}", headers=h)).json()["data"]["rows"] == []
    assert (await ac.get(f"{R}?report=complaints&status=closed", headers=h)).status_code == 422
    assert (await ac.get(f"{R}?report=batch_expiry&status=weird", headers=h)).status_code == 422
    # A filter that does not apply is refused, never silently ignored.
    bad = await ac.get(f"{R}?report=recalls&product_id={a.id}", headers=h)
    assert bad.status_code == 422 and "product_id" in str(bad.json())
    assert (await ac.get(f"{R}?report=sales_by_product&product_id=not-a-uuid", headers=h)).status_code == 422
    cat = (await ac.get(f"{API}/reports/centre", headers=h)).json()["data"]
    assert all("filters" in c for c in cat) and [c for c in cat if c["id"] == "recalls"][0]["filters"] == ["status"]


@pytest.mark.asyncio
async def test_filters_cannot_reach_another_companys_data(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, oa = await _sell(ac, h, db_session, seed, "Cola")
    from app.rbac import permissions_for_role
    from app.security import hash_password
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    db_session.add(m.User(tenant_id=seed["t2"].id, email="admin@beta.example.com", full_name="Beta", password_hash=hash_password("SecurePass123!"),
                          role="company_admin", email_verified=True, permissions=permissions_for_role("company_admin"), totp_enabled=False))
    await db_session.commit()
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    r = await ac.get(f"{R}?report=sales_by_product&product_id={a.id}&outlet_id={oa}", headers=other)
    assert r.status_code == 200 and r.json()["data"]["rows"] == []
    assert a.name not in str(r.json())
    for fmt in ("xlsx", "pdf", "csv"):
        assert (await ac.get(f"{R}?report=stock_valuation&product_id={a.id}&format={fmt}", headers=other)).status_code == 200
