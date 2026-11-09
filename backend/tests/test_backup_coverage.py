"""A company backup holds every business record, in an order a restore can actually use."""

from __future__ import annotations

import json

import pyotp
import pytest
from sqlalchemy import select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers


def _company_tables() -> set[str]:
    return {table.name for table in m.Base.metadata.tables.values() if "tenant_id" in table.columns}


def _backed_up() -> dict[str, type]:
    return {model.__table__.name: model for _name, model in backup_svc.DATASET_SPECS}


def test_every_company_table_is_backed_up_or_has_a_reason_not_to_be():
    decided = set(_backed_up()) | set(backup_svc.BACKUP_EXCLUDED)
    assert _company_tables() - decided == set()


def test_a_table_is_never_both_backed_up_and_excluded():
    assert set(_backed_up()) & set(backup_svc.BACKUP_EXCLUDED) == set()


def test_exclusions_name_real_tables_and_give_a_reason():
    for table, reason in backup_svc.BACKUP_EXCLUDED.items():
        assert table in m.Base.metadata.tables, table
        assert len(reason) > 20, table


def test_sign_in_material_never_goes_into_a_backup():
    for table in ("users", "auth_sessions", "auth_tokens", "api_keys", "two_factor_backup_codes", "pos_cashier_passcodes"):
        assert table not in _backed_up()
    assert backup_svc._is_secret_column("session_token")
    assert backup_svc._is_secret_column("password_hash")


def test_a_row_is_only_restored_after_what_it_must_point_at():
    """A required link cannot be filled in later, so its parent has to come first."""
    position = {name: index for index, name in enumerate(_backed_up())}
    for name, model in _backed_up().items():
        for fk in model.__table__.foreign_keys:
            parent = fk.column.table.name
            if parent in position and not fk.parent.nullable:
                assert position[parent] < position[name], f"{name}.{fk.parent.name} needs {parent} first"


def test_every_link_pointing_forward_can_wait_until_the_end():
    for name, model in _backed_up().items():
        for column in backup_svc._late_columns(model):
            assert model.__table__.columns[column].nullable, f"{name}.{column}"


def test_a_required_stripped_column_has_a_way_back():
    """A lost row needs every required column. Only shoppers lose one, and restore gives it back."""
    for name, model in _backed_up().items():
        stripped = [
            c.name
            for c in model.__table__.columns
            if backup_svc._is_secret_column(c.name) and not c.nullable and c.default is None and c.server_default is None
        ]
        assert stripped in ([], ["password_hash"]), (name, stripped)
        if stripped:
            assert model is m.EcommerceShopper


@pytest.mark.asyncio
async def test_lost_sales_records_come_back(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    h = await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)
    tenant_id = seed["t1"].id
    group = m.CustomerGroup(tenant_id=tenant_id, name="Trade", code="TRD", discount_percent=5)
    branch = m.Branch(tenant_id=tenant_id, name="Tema", code="TMA")
    customer = m.Party(tenant_id=tenant_id, kind="customer", name="Akua Stores", status="active", credit_limit=0)
    db_session.add_all([group, branch, customer])
    await db_session.flush()
    quote = m.SalesQuotation(tenant_id=tenant_id, quotation_number="QT-AUDIT-1", customer_id=customer.id, status="draft")
    db_session.add(quote)
    await db_session.flush()
    order = m.SalesOrder(
        tenant_id=tenant_id, order_number="SO-AUDIT-1", customer_id=customer.id, status="draft", quotation_id=quote.id
    )
    db_session.add(order)
    await db_session.commit()

    payload, counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    for name in ("sales_quotations", "sales_orders", "customer_groups", "branches"):
        assert counts[name] >= 1, name

    ids = {m.SalesOrder: order.id, m.SalesQuotation: quote.id, m.CustomerGroup: group.id, m.Branch: branch.id}
    for row in (order, quote, group, branch):
        await db_session.delete(row)
    await db_session.commit()

    report = await backup_svc.apply_restore(db_session, tenant_id, json.loads(json.dumps(payload, default=str)))
    await db_session.commit()
    assert report["proof"]["ok"] is True
    for model, pk in ids.items():
        assert (await db_session.execute(select(model).where(model.id == pk))).scalar_one_or_none() is not None
    back = await db_session.get(m.SalesOrder, ids[m.SalesOrder])
    assert back.quotation_id == ids[m.SalesQuotation]


@pytest.mark.asyncio
async def test_a_lost_shopper_comes_back_without_any_old_password(client, seeded, db_session):
    tenant_id = client[1]["t1"].id
    shopper = m.EcommerceShopper(tenant_id=tenant_id, email="ama@example.com", password_hash="old-hash", name="Ama")
    db_session.add(shopper)
    await db_session.commit()
    payload, _counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    assert "old-hash" not in json.dumps(payload["datasets"]["ecommerce_shoppers"])
    pk = shopper.id
    await db_session.delete(shopper)
    await db_session.commit()

    await backup_svc.apply_restore(db_session, tenant_id, json.loads(json.dumps(payload, default=str)))
    await db_session.commit()
    back = await db_session.get(m.EcommerceShopper, pk)
    assert back is not None
    assert back.password_hash not in {"", "old-hash"}


@pytest.mark.asyncio
async def test_restoring_over_recreated_default_accounts_leaves_one_of_each(client, seeded, db_session):
    tenant_id = client[1]["t1"].id
    kept = m.Account(tenant_id=tenant_id, code="9901", name="Kept", account_type="asset")
    db_session.add(kept)
    await db_session.commit()
    payload, _counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    pk = kept.id
    await db_session.delete(kept)
    await db_session.flush()
    db_session.add(m.Account(tenant_id=tenant_id, code="9901", name="Recreated", account_type="asset"))
    await db_session.commit()

    await backup_svc.apply_restore(db_session, tenant_id, json.loads(json.dumps(payload, default=str)))
    await db_session.commit()
    rows = (
        await db_session.execute(select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "9901"))
    ).scalars().all()
    assert [row.id for row in rows] == [pk]


@pytest.mark.asyncio
async def test_a_failed_restore_undoes_itself_and_says_so(client, seeded, db_session):
    """Posted entries on a recreated account stop the restore cleanly, with nothing half done."""
    from fastapi import HTTPException

    ac, seed = client
    tenant_id = seed["t1"].id
    kept = m.Account(tenant_id=tenant_id, code="9902", name="Kept", account_type="asset")
    db_session.add(kept)
    await db_session.commit()
    job = await backup_svc.create_backup(db_session, tenant_id=tenant_id, user_id=seed["super"].id)
    await db_session.commit()
    await db_session.delete(kept)
    await db_session.flush()
    recreated = m.Account(tenant_id=tenant_id, code="9902", name="Recreated", account_type="asset")
    db_session.add(recreated)
    await db_session.flush()
    entry = m.JournalEntry(tenant_id=tenant_id, entry_number="JE-DRILL-1", description="Posted after the backup")
    db_session.add(entry)
    await db_session.flush()
    db_session.add(
        m.JournalEntryLine(tenant_id=tenant_id, journal_entry_id=entry.id, account_id=recreated.id, debit=5, credit=0)
    )
    await db_session.commit()

    with pytest.raises(HTTPException) as caught:
        await backup_svc.restore_backup(
            db_session,
            tenant_id=tenant_id,
            backup_id=job.id,
            dry_run=False,
            confirm=True,
            user_id=seed["super"].id,
        )
    assert caught.value.status_code == 409
    await db_session.commit()
    rows = (
        await db_session.execute(select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "9902"))
    ).scalars().all()
    assert [row.name for row in rows] == ["Recreated"]


@pytest.mark.asyncio
async def test_a_company_backup_never_reads_another_desks_tables(client, seeded, db_session):
    """Hotel, restaurant and retail stay apart, even for a stray row under the same company."""
    from tests.conftest import set_tenant_industry

    tenant_id = client[1]["t1"].id
    db_session.add(m.HotelRoom(tenant_id=tenant_id, code="STRAY", name="Stray", rate_amount=1, status="available"))
    db_session.add(m.RestaurantTable(tenant_id=tenant_id, code="STRAY", name="Stray"))
    await db_session.commit()

    await set_tenant_industry(db_session, client[1]["t1"], "retail")
    _payload, counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    assert counts["hotel_rooms"] == 0 and counts["restaurant_tables"] == 0

    await set_tenant_industry(db_session, client[1]["t1"], "hotel")
    _payload, counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    assert counts["hotel_rooms"] == 1 and counts["restaurant_tables"] == 0

    await set_tenant_industry(db_session, client[1]["t1"], "restaurant")
    _payload, counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    assert counts["hotel_rooms"] == 0 and counts["restaurant_tables"] == 1


@pytest.mark.asyncio
async def test_an_fmcg_company_keeps_its_own_tables_in_its_backup(client, seeded, db_session):
    """FMCG is not a selectable business type, so the check must read the stored value."""
    from tests.conftest import set_tenant_industry

    tenant_id = client[1]["t1"].id
    db_session.add(m.FmcgRoute(tenant_id=tenant_id, code="R1", name="Accra East"))
    await db_session.commit()
    await set_tenant_industry(db_session, client[1]["t1"], "fmcg")
    _payload, counts = await backup_svc.collect_tenant_payload(db_session, tenant_id)
    assert counts["fmcg_routes"] == 1


@pytest.mark.asyncio
async def test_only_a_hotels_tax_filing_reads_hotel_shop_sales(client, seeded, db_session):
    from app import tax as tax_svc
    from tests.conftest import set_tenant_industry

    tenant_id = client[1]["t1"].id
    db_session.add(
        m.HotelShopSale(
            tenant_id=tenant_id, sale_number="HS-STRAY", payment_method="cash", status="completed",
            subtotal=100, tax=20, total=120,
        )
    )
    await db_session.commit()
    await set_tenant_industry(db_session, client[1]["t1"], "retail")
    assert (await tax_svc.tax_filing_pack(db_session, tenant_id))["output_tax"] == 0
    await set_tenant_industry(db_session, client[1]["t1"], "hotel")
    assert (await tax_svc.tax_filing_pack(db_session, tenant_id))["output_tax"] == 20

