"""Restaurant digital menu: management, the public guest menu, QR codes and isolation."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _restaurant(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _dish(ac, admin, name="Jollof", price=30, station="kitchen", category="Mains"):
    r = await ac.post(
        "/api/v1/products", headers=admin,
        json={"name": name, "selling_price": price, "cost_price": 11, "stock_qty": 50,
              "prep_station": station, "category": category},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _menu(ac, admin):
    r = await ac.get("/api/v1/restaurant/menu", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _publish(ac, admin):
    r = await ac.patch("/api/v1/restaurant/menu/settings", headers=admin, json={"is_published": True})
    assert r.status_code == 200, r.text
    return r.json()["data"]["public_token"]


async def test_first_visit_lays_out_existing_dishes_by_category(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin, "Jollof", 30, "kitchen", "Mains")
    await _dish(ac, admin, "Sobolo", 8, "bar", "General")
    data = await _menu(ac, admin)
    names = {c["name"]: [i["name"] for i in c["items"]] for c in data["categories"]}
    assert names == {"Drinks": ["Sobolo"], "Mains": ["Jollof"]}
    assert data["settings"]["is_published"] is False


async def test_menu_is_private_until_published_then_public_without_login(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    token = (await _menu(ac, admin))["settings"]["public_token"]
    assert (await ac.get(f"/api/v1/public/menu/{token}")).status_code == 404
    await _publish(ac, admin)
    r = await ac.get(f"/api/v1/public/menu/{token}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["restaurant"]["name"] == "Alpha Co"
    assert data["categories"][0]["items"][0]["name"] == "Jollof"
    assert data["categories"][0]["items"][0]["price"] == 30


async def test_public_menu_carries_no_private_business_data(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    product_id = await _dish(ac, admin)
    token = (await _menu(ac, admin))["settings"]["public_token"]
    await _publish(ac, admin)
    text = (await ac.get(f"/api/v1/public/menu/{token}")).text
    for private in ("cost_price", "stock_qty", "sku", "tenant_id", seed["t1"].id, product_id, "email"):
        assert private not in text, private
    item = json.loads(text)["data"]["categories"][0]["items"][0]
    assert set(item) == {"id", "name", "description", "price", "image_version", "available", "featured", "promo"}


async def test_edits_show_on_the_same_link_and_price_reaches_the_till(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    product_id = await _dish(ac, admin)
    data = await _menu(ac, admin)
    token = data["settings"]["public_token"]
    item_id = data["categories"][0]["items"][0]["id"]
    await _publish(ac, admin)
    before = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["version"]
    r = await ac.patch(
        f"/api/v1/restaurant/menu/items/{item_id}", headers=admin,
        json={"name": "Smoky Jollof", "price": 35.5, "description": "Party rice with smoked chicken",
              "is_featured": True, "promo_label": "Chef's pick"},
    )
    assert r.status_code == 200, r.text
    after = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]
    assert after["version"] != before
    shown = after["categories"][0]["items"][0]
    assert (shown["name"], shown["price"], shown["promo"]) == ("Smoky Jollof", 35.5, "Chef's pick")
    product = await ac.get(f"/api/v1/products/{product_id}", headers=admin)
    assert float(product.json()["data"]["selling_price"]) == 35.5


async def test_etag_lets_the_board_skip_unchanged_menus(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    token = (await _menu(ac, admin))["settings"]["public_token"]
    await _publish(ac, admin)
    first = await ac.get(f"/api/v1/public/menu/{token}")
    again = await ac.get(f"/api/v1/public/menu/{token}", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304


async def test_unavailable_items_are_marked_or_hidden(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    token = data["settings"]["public_token"]
    item_id = data["categories"][0]["items"][0]["id"]
    await _publish(ac, admin)
    r = await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=admin, json={"available": False})
    assert r.status_code == 200 and r.json()["data"]["available"] is False
    shown = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]
    assert shown["categories"][0]["items"][0]["available"] is False
    await ac.patch("/api/v1/restaurant/menu/settings", headers=admin, json={"show_unavailable": False})
    assert (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["categories"] == []
    await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=admin, json={"available": True})
    assert (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["categories"][0]["items"][0]["available"]


async def test_unpublished_items_and_categories_stay_hidden(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin, "Shown", category="Mains")
    await _dish(ac, admin, "Hidden", category="Mains")
    await _dish(ac, admin, "Secret", category="Specials")
    data = await _menu(ac, admin)
    token = data["settings"]["public_token"]
    await _publish(ac, admin)
    by_name = {i["name"]: i for c in data["categories"] for i in c["items"]}
    specials = next(c for c in data["categories"] if c["name"] == "Specials")
    await ac.patch(f"/api/v1/restaurant/menu/items/{by_name['Hidden']['id']}", headers=admin, json={"is_published": False})
    await ac.patch(f"/api/v1/restaurant/menu/categories/{specials['id']}", headers=admin, json={"is_published": False})
    shown = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["categories"]
    assert [i["name"] for c in shown for i in c["items"]] == ["Shown"]


async def test_category_and_item_order_is_kept(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin, "Alpha", category="Starters")
    await _dish(ac, admin, "Beta", category="Starters")
    await _dish(ac, admin, "Gamma", category="Mains")
    data = await _menu(ac, admin)
    token = data["settings"]["public_token"]
    await _publish(ac, admin)
    ids = [c["id"] for c in data["categories"]]
    assert (await ac.put(
        "/api/v1/restaurant/menu/categories/order", headers=admin, json={"ids": list(reversed(ids))}
    )).status_code == 200
    starters = next(c for c in data["categories"] if c["name"] == "Starters")
    assert (await ac.put(
        f"/api/v1/restaurant/menu/categories/{starters['id']}/items/order", headers=admin,
        json={"ids": [i["id"] for i in reversed(starters["items"])]},
    )).status_code == 200
    shown = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["categories"]
    assert [c["name"] for c in shown] == ["Starters", "Mains"]
    assert [i["name"] for i in shown[0]["items"]] == ["Beta", "Alpha"]


async def test_add_new_dish_from_the_menu_screen_reaches_the_till(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _menu(ac, admin)
    category = await ac.post("/api/v1/restaurant/menu/categories", headers=admin, json={"name": "Grill"})
    assert category.status_code == 200, category.text
    item = await ac.post(
        "/api/v1/restaurant/menu/items", headers=admin,
        json={"category_id": category.json()["data"]["id"], "name": "Grilled tilapia", "price": 85, "station": "kitchen"},
    )
    assert item.status_code == 200, item.text
    row = await db_session.get(m.Product, item.json()["data"]["product_id"])
    assert row.prep_station == "kitchen" and float(row.selling_price) == 85
    assert (await ac.post(
        "/api/v1/restaurant/menu/items", headers=admin,
        json={"category_id": category.json()["data"]["id"], "product_id": row.id},
    )).status_code == 409


async def test_category_with_dishes_cannot_be_deleted(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    category = data["categories"][0]
    assert (await ac.delete(f"/api/v1/restaurant/menu/categories/{category['id']}", headers=admin)).status_code == 409
    item = category["items"][0]["id"]
    assert (await ac.delete(f"/api/v1/restaurant/menu/items/{item}", headers=admin)).status_code == 200
    assert (await ac.delete(f"/api/v1/restaurant/menu/categories/{category['id']}", headers=admin)).status_code == 200
    again = await _menu(ac, admin)
    assert [d["name"] for d in again["unlisted"]] == ["Jollof"]


async def test_photo_upload_serves_publicly_only_while_published(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    token = data["settings"]["public_token"]
    item_id = data["categories"][0]["items"][0]["id"]
    await _publish(ac, admin)
    up = await ac.post(
        f"/api/v1/restaurant/menu/items/{item_id}/photo",
        headers=admin,
        files={"file": ("dish.png", PNG, "image/png")},
    )
    assert up.status_code == 200, up.text
    shown = (await ac.get(f"/api/v1/public/menu/{token}")).json()["data"]["categories"][0]["items"][0]
    assert shown["image_version"]
    assert (await ac.get(f"/api/v1/public/menu/{token}/items/{item_id}/image")).status_code == 200
    await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=admin, json={"is_published": False})
    assert (await ac.get(f"/api/v1/public/menu/{token}/items/{item_id}/image")).status_code == 404


async def test_qr_png_and_printable_card_download(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    png = await ac.get("/api/v1/restaurant/menu/qr.png?size=large", headers=admin)
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
    assert "attachment" in png.headers["content-disposition"]
    pdf = await ac.get("/api/v1/restaurant/menu/qr.pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


async def test_qr_encodes_this_restaurants_public_menu(client, db_session):
    from app import restaurant_menu

    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    settings = (await _menu(ac, admin))["settings"]
    assert settings["public_url"] == restaurant_menu.menu_url(settings["public_token"])
    assert settings["public_url"].endswith(f"/menu/{settings['public_token']}")
    assert settings["board_url"] == settings["public_url"] + "/board"


async def test_regenerating_kills_the_old_link_and_menu_edits_do_not(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    old = data["settings"]["public_token"]
    await _publish(ac, admin)
    await ac.patch(
        f"/api/v1/restaurant/menu/items/{data['categories'][0]['items'][0]['id']}", headers=admin, json={"price": 40}
    )
    assert (await _menu(ac, admin))["settings"]["public_token"] == old
    r = await ac.post("/api/v1/restaurant/menu/regenerate-link", headers=admin)
    new = r.json()["data"]["public_token"]
    assert new != old
    assert (await ac.get(f"/api/v1/public/menu/{old}")).status_code == 404
    assert (await ac.get(f"/api/v1/public/menu/{new}")).status_code == 200


async def test_one_restaurant_cannot_touch_another_restaurants_menu(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await set_tenant_industry(db_session, seed["t2"], "restaurant")
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    category = data["categories"][0]
    item = category["items"][0]
    other = m.User(
        tenant_id=seed["t2"].id, email="boss@beta.example.com", full_name="Beta Boss",
        password_hash=seed["u2"].password_hash, role="company_admin", email_verified=True,
        permissions=__import__("app.rbac", fromlist=["x"]).permissions_for_role("company_admin"),
    )
    db_session.add(other)
    await db_session.commit()
    beta = await auth_headers(ac, email="boss@beta.example.com", tenant_slug="beta")
    assert (await ac.patch(f"/api/v1/restaurant/menu/items/{item['id']}", headers=beta, json={"price": 1})).status_code == 404
    assert (await ac.delete(f"/api/v1/restaurant/menu/items/{item['id']}", headers=beta)).status_code == 404
    assert (await ac.patch(f"/api/v1/restaurant/menu/categories/{category['id']}", headers=beta, json={"name": "X"})).status_code == 404
    assert (await ac.post(f"/api/v1/restaurant/menu/items/{item['id']}/photo", headers=beta, files={"file": ("d.png", PNG, "image/png")})).status_code == 404
    mine = await _menu(ac, beta)
    assert mine["categories"] == [] and mine["settings"]["public_token"] != data["settings"]["public_token"]


async def test_public_image_of_another_restaurant_is_refused(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await set_tenant_industry(db_session, seed["t2"], "restaurant")
    await _dish(ac, admin)
    data = await _menu(ac, admin)
    item_id = data["categories"][0]["items"][0]["id"]
    db_session.add(m.RestaurantMenuSettings(tenant_id=seed["t2"].id, public_token="beta-public-token-0001", is_published=True))
    await db_session.commit()
    assert (await ac.get(f"/api/v1/public/menu/beta-public-token-0001/items/{item_id}/image")).status_code == 404


async def test_suspended_restaurant_menu_goes_dark(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    token = (await _menu(ac, admin))["settings"]["public_token"]
    await _publish(ac, admin)
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    tenant.status = "suspended"
    await db_session.commit()
    assert (await ac.get(f"/api/v1/public/menu/{token}")).status_code == 404


async def test_only_managers_change_the_menu(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    item_id = (await _menu(ac, admin))["categories"][0]["items"][0]["id"]
    for role in ("restaurant_waiter", "restaurant_cashier", "restaurant_kitchen"):
        email = f"{role}@alpha.example.com"
        made = await ac.post(
            "/api/v1/users", headers=admin,
            json={"email": email, "full_name": role.title().replace("_", " "), "password": "SecurePass123!", "role": role},
        )
        assert made.status_code == 200, made.text
        staff = await auth_headers(ac, email=email, tenant_slug="alpha")
        r = await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=staff, json={"price": 1})
        assert r.status_code == 403, role
    manager = await ac.post(
        "/api/v1/users", headers=admin,
        json={"email": "rm@alpha.example.com", "full_name": "Rest Manager", "password": "SecurePass123!", "role": "restaurant_manager"},
    )
    assert manager.status_code == 200
    staff = await auth_headers(ac, email="rm@alpha.example.com", tenant_slug="alpha")
    assert (await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=staff, json={"price": 32})).status_code == 200


async def test_retail_companies_have_no_menu(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/restaurant/menu", headers=admin)
    assert r.status_code in {403, 404}


async def test_price_change_is_audited(client, db_session):
    ac, seed = client
    admin = await _restaurant(ac, seed, db_session)
    await _dish(ac, admin)
    item_id = (await _menu(ac, admin))["categories"][0]["items"][0]["id"]
    await ac.patch(f"/api/v1/restaurant/menu/items/{item_id}", headers=admin, json={"price": 44})
    log = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "restaurant_menu_item_updated"))
    ).scalar_one()
    assert log.details["price"] == {"before": 30, "after": 44}
