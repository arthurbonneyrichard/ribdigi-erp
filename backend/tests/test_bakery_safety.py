"""Food safety: temperature points, readings that need an action, signed checklists, inspector record."""

from __future__ import annotations

import pytest

from tests.test_bakery_desk import _owner

B = "/api/v1/bakery/safety"


async def _point(ac, h, name="Walk-in fridge", kind="fridge", **kw):
    r = await ac.post(f"{B}/points", headers=h, json={"name": name, "kind": kind, **kw})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_readings_need_an_action_when_out_of_range(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    p = await _point(ac, h)
    assert p["min_c"] == 0 and p["max_c"] == 5  # fridge defaults

    ok = await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": 3.4})
    assert ok.status_code == 200 and ok.json()["data"]["in_range"] is True

    bad = await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": 9})
    assert bad.status_code == 400  # no action written

    junk = await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": 9, "action_taken": "!!!"})
    assert junk.status_code == 400

    done = await ac.post(
        f"{B}/readings", headers=h,
        json={"point_id": p["id"], "reading_c": 9, "action_taken": "Moved stock to second fridge and called engineer"},
    )
    assert done.status_code == 200 and done.json()["data"]["in_range"] is False

    s = (await ac.get(B, headers=h)).json()["data"]
    row = next(x for x in s["points"] if x["id"] == p["id"])
    assert row["taken_today"] == 2 and row["out_of_range_today"] == 1 and row["still_due"] == 0
    assert s["bad_readings_today"] == 1


@pytest.mark.asyncio
async def test_checklist_and_inspector_record(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    p = await _point(ac, h, name="Oven 1", kind="oven")
    await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": 220})

    partial = await ac.post(f"{B}/checks", headers=h, json={"kind": "opening", "done": [0, 1]})
    assert partial.status_code == 200 and partial.json()["data"]["all_done"] is False
    s = (await ac.get(B, headers=h)).json()["data"]
    assert next(c for c in s["checklists"] if c["kind"] == "opening")["done_today"] is False

    full = await ac.post(f"{B}/checks", headers=h, json={"kind": "opening", "done": list(range(6))})
    assert full.json()["data"]["all_done"] is True
    s = (await ac.get(B, headers=h)).json()["data"]
    assert next(c for c in s["checklists"] if c["kind"] == "opening")["done_today"] is True

    assert (await ac.post(f"{B}/checks", headers=h, json={"kind": "opening", "done": [99]})).status_code == 422

    page = await ac.get(f"{B}/print", headers=h)
    assert page.status_code == 200 and "Food safety record" in page.text and "Oven 1" in page.text
    hist = (await ac.get(f"{B}/history", headers=h)).json()["data"]
    assert len(hist["readings"]) == 1 and len(hist["checks"]) == 2
    assert (await ac.get(f"{B}/history?start_date=2026-12-01&end_date=2026-11-01", headers=h)).status_code == 422


@pytest.mark.asyncio
async def test_point_rules_and_duplicates(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    p = await _point(ac, h, name="Freezer", kind="freezer")
    assert p["min_c"] == -25 and p["max_c"] == -18
    dup = await ac.post(f"{B}/points", headers=h, json={"name": "Freezer", "kind": "freezer"})
    assert dup.status_code == 409
    inverted = await ac.post(f"{B}/points", headers=h, json={"name": "Odd", "kind": "fridge", "min_c": 8, "max_c": 2})
    assert inverted.status_code == 422
    off = await ac.patch(f"{B}/points/{p['id']}", headers=h, json={"is_active": False})
    assert off.status_code == 200
    gone = await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": -20})
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_cake_options_price_and_note_an_order(client, seeded, db_session):
    from datetime import date, timedelta

    from tests.test_bakery_desk import _product

    ac, seed = client
    h = await _owner(ac, seed, db_session)
    cake = await _product(db_session, seed, "Celebration cake", price=100)
    opts = [
        {"name": "Size", "required": True, "choices": [{"label": "6 inch", "extra": 0}, {"label": "10 inch", "extra": 60}]},
        {"name": "Flavour", "choices": [{"label": "Vanilla"}, {"label": "Red velvet", "extra": 15}]},
    ]
    r = await ac.put(f"/api/v1/bakery/items/{cake.id}/details", headers=h, json={"options": opts})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["options"][0]["choices"][1]["extra"] == 60

    bad = await ac.put(f"/api/v1/bakery/items/{cake.id}/details", headers=h, json={"options": [{"name": "Size", "choices": [{"label": "!!!"}]}]})
    assert bad.status_code in (400, 422)

    due = (date.today() + timedelta(days=2)).isoformat()
    body = {"customer_name": "Efua Mensah", "due_date": due}

    missing = await ac.post("/api/v1/bakery/orders", headers=h, json={**body, "lines": [{"product_id": cake.id, "quantity": 1}]})
    assert missing.status_code == 422 and "Size" in missing.text

    wrong = await ac.post("/api/v1/bakery/orders", headers=h, json={**body, "lines": [{"product_id": cake.id, "quantity": 1, "options": [{"group": "Size", "choice": "3 foot"}]}]})
    assert wrong.status_code == 422

    ok = await ac.post(
        "/api/v1/bakery/orders", headers=h,
        json={**body, "lines": [{
            "product_id": cake.id, "quantity": 2, "note": "Happy 30th Ama",
            "options": [{"group": "size", "choice": "10 inch"}, {"group": "Flavour", "choice": "Red velvet"}],
        }]},
    )
    assert ok.status_code == 200, ok.text
    order = ok.json()["data"]
    assert float(order["total"]) == 2 * (100 + 60 + 15)
    note = order["items"][0]["note"]
    assert "Size: 10 inch" in note and "Flavour: Red velvet" in note and "Happy 30th Ama" in note


@pytest.mark.asyncio
async def test_dashboard_flags_bad_and_missing_readings(client, seeded, db_session):
    ac, seed = client
    h = await _owner(ac, seed, db_session)
    p = await _point(ac, h)
    dash = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    assert any("still to take" in a["text"] and a["href"] == "/bakery?tab=safety" for a in dash["attention"]), dash["attention"]
    await ac.post(f"{B}/readings", headers=h, json={"point_id": p["id"], "reading_c": 12, "action_taken": "Called the engineer"})
    dash = (await ac.get("/api/v1/bakery/summary", headers=h)).json()["data"]
    assert any("outside the safe range" in a["text"] for a in dash["attention"])
