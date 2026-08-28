"""Store-scoped dashboard resolution for Store Managers (Stage 81 S1 / ADR-005 adjacency).

Also used for operational list/read hardening (POS sales, sales invoices, expenses,
transfers, warehouses / inventory movements) and accounting statement reads
(P&L / TB / cash-flow / balance-sheet) and bank recon unmatched book lines — still
``stores.manager_id`` only;
ADR-005 membership tables remain deferred. Warehouse scope maps via
``Warehouse.store_id`` ∈ managed stores. POS holds scope via
``PosSession.store_id``; drawer-settings export uses managed store IDs.
POS sale receipt get/send scopes via ``PosSession.store_id`` (null session fail-closed).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import exists, or_, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.dashboard_views import dashboard_view_for_role


async def managed_store_ids(db: AsyncSession, claims: dict) -> list[str] | None:
    """Return managed store IDs for store_manager view; None means tenant-wide (no store filter).

    Uses ``stores.manager_id`` only (ADR-005 — no user↔store membership table).
    """
    role = (claims.get("role") or "").strip().lower()
    if dashboard_view_for_role(role) != "store_manager":
        return None
    user_id = claims.get("sub")
    tenant_id = claims.get("tenant_id")
    if not user_id or not tenant_id:
        return []
    rows = (
        await db.execute(
            select(m.Store.id).where(
                m.Store.tenant_id == tenant_id,
                m.Store.manager_id == user_id,
                m.Store.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    return [str(sid) for sid in rows]


def store_scope_payload(store_ids: list[str] | None) -> dict:
    if store_ids is None:
        return {"mode": "tenant", "store_ids": [], "managed_store_count": None}
    return {
        "mode": "managed_stores",
        "store_ids": list(store_ids),
        "managed_store_count": len(store_ids),
    }


def assert_store_in_manager_scope(
    managed_ids: list[str] | None,
    store_id: str | None,
    *,
    allow_unset: bool = True,
) -> None:
    """403 when a store_manager requests a store outside ``manager_id`` scope.

    When ``allow_unset`` is False, missing ``store_id`` is also denied (fail closed
    for records that should be store-bound for managers).
    """
    if managed_ids is None:
        return
    sid = (store_id or "").strip()
    if not sid:
        if allow_unset:
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Record has no store assignment within your managed store scope.",
                "store_id": None,
            },
        )
    if sid not in managed_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Store is outside your managed store scope.",
                "store_id": sid,
            },
        )


def assert_offline_sync_store_scope(
    managed_ids: list[str] | None,
    store_id: str | None,
    *,
    message: str = "Store managers must bind offline sync to a managed store.",
) -> None:
    """403 when store_manager sync push/pull/ack uses foreign or unset ``store_id``.

    Mirrors offline device bind: envelope refresh on ``/sync/push``,
    ``/sync/pull``, and ``/sync/ack`` must not company-bind or touch unmanaged
    stores. Register / revoke remain admin; Offline Complete remains MISSING.
    """
    if managed_ids is None:
        return
    sid = (store_id or "").strip()
    if not sid:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": message,
                "store_id": None,
            },
        )
    if sid not in managed_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": message,
                "store_id": sid,
            },
        )


async def assert_pos_session_store_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    session_id: str | None,
    *,
    require_session: bool = False,
) -> None:
    """403 when a store_manager references a POS session outside managed stores.

    Held carts have no ``store_id``; scope follows ``PosSession.store_id``.
    When ``require_session`` is True, missing ``session_id`` is denied.
    """
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    sid = (session_id or "").strip() or None
    if not sid:
        assert_store_in_manager_scope(managed, None, allow_unset=not require_session)
        return
    session = await db.get(m.PosSession, sid)
    if not session or session.tenant_id != claims.get("tenant_id"):
        raise HTTPException(status_code=404, detail="POS session not found")
    company_id = claims.get("company_id")
    if company_id and session.company_id and session.company_id != company_id:
        raise HTTPException(status_code=404, detail="POS session not found")
    assert_store_in_manager_scope(
        managed, getattr(session, "store_id", None), allow_unset=False
    )


async def assert_pos_sale_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    sale_id: str,
) -> None:
    """403 when a store_manager reads or sends a receipt for a POS sale outside managed stores.

    Scope follows ``PosSession.store_id`` via ``Transaction.session_id``; null session
    fail-closed (same as POS holds).
    """
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    sid = (sale_id or "").strip()
    if not sid:
        raise HTTPException(status_code=404, detail="POS sale not found")
    tx = (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.id == sid,
                m.Transaction.tenant_id == claims.get("tenant_id"),
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="POS sale not found")
    company_id = claims.get("company_id")
    if company_id and tx.company_id and tx.company_id != company_id:
        raise HTTPException(status_code=404, detail="POS sale not found")
    session = None
    if tx.session_id:
        session = await db.get(m.PosSession, tx.session_id)
        if not session or session.tenant_id != claims.get("tenant_id"):
            raise HTTPException(status_code=404, detail="POS sale not found")
        if company_id and session.company_id and session.company_id != company_id:
            raise HTTPException(status_code=404, detail="POS sale not found")
    assert_store_in_manager_scope(
        managed,
        getattr(session, "store_id", None) if session else None,
        allow_unset=False,
    )


async def assert_journal_line_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    journal_line_id: str,
    managed_ids: list[str] | None,
) -> None:
    """403 when a store_manager references a journal line outside managed stores."""
    if managed_ids is None:
        return
    jid = (journal_line_id or "").strip()
    if not jid:
        raise HTTPException(status_code=400, detail="journal_line_id required")
    row = (
        await db.execute(
            select(m.JournalEntryLine, m.JournalEntry)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .where(
                m.JournalEntryLine.id == jid,
                m.JournalEntryLine.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Journal line not found")
    _line, entry = row
    assert_store_in_manager_scope(
        managed_ids, getattr(entry, "store_id", None), allow_unset=False
    )


def assert_transfer_touches_manager_scope(
    managed_ids: list[str] | None,
    *,
    from_store_id: str | None,
    to_store_id: str | None,
) -> None:
    """403 unless transfer involves at least one managed store (store_manager)."""
    if managed_ids is None:
        return
    touched = {
        sid
        for sid in ((from_store_id or "").strip(), (to_store_id or "").strip())
        if sid
    }
    if not touched or touched.isdisjoint(set(managed_ids)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Stock transfer is outside your managed store scope.",
                "from_store_id": from_store_id,
                "to_store_id": to_store_id,
            },
        )


def constrain_store_query(
    managed_ids: list[str] | None,
    requested_store_id: str | None = None,
) -> tuple[str | None, list[str] | None]:
    """Resolve list filters for store_manager.

    Returns ``(single_store_id, store_ids_in)``:
    - tenant-wide roles: ``(requested, None)``
    - store_manager with request: validates then ``(requested, None)``
    - store_manager without request: ``(None, managed_ids)`` (may be empty)
    """
    req = (requested_store_id or "").strip() or None
    if managed_ids is None:
        return req, None
    if req:
        assert_store_in_manager_scope(managed_ids, req)
        return req, None
    return None, list(managed_ids)


async def managed_warehouse_ids(db: AsyncSession, claims: dict) -> list[str] | None:
    """Warehouse IDs linked to managed stores; None = tenant-wide; [] = none.

    Warehouses with null ``store_id`` (central / unassigned) are out of store_manager
    scope. Still ``stores.manager_id`` only — ADR-005 deferred.
    """
    managed_stores = await managed_store_ids(db, claims)
    if managed_stores is None:
        return None
    if not managed_stores:
        return []
    stmt = select(m.Warehouse.id).where(
        m.Warehouse.tenant_id == claims["tenant_id"],
        m.Warehouse.store_id.in_(managed_stores),
    )
    company_id = claims.get("company_id")
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [str(wid) for wid in rows]


def assert_warehouse_in_manager_scope(
    managed_wh_ids: list[str] | None,
    warehouse_id: str | None,
    *,
    allow_unset: bool = True,
) -> None:
    """403 when a store_manager targets a warehouse outside managed-store WHs."""
    if managed_wh_ids is None:
        return
    wid = (warehouse_id or "").strip()
    if not wid:
        if allow_unset:
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Warehouse is required within your managed store scope.",
                "warehouse_id": None,
            },
        )
    if wid not in managed_wh_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Warehouse is outside your managed store scope.",
                "warehouse_id": wid,
            },
        )


def constrain_warehouse_query(
    managed_wh_ids: list[str] | None,
    requested_warehouse_id: str | None = None,
) -> tuple[str | None, list[str] | None]:
    """Resolve warehouse list filters for store_manager (mirrors constrain_store_query)."""
    req = (requested_warehouse_id or "").strip() or None
    if managed_wh_ids is None:
        return req, None
    if req:
        assert_warehouse_in_manager_scope(managed_wh_ids, req)
        return req, None
    return None, list(managed_wh_ids)


def apply_warehouse_scope_filter(stmt, model, managed_wh_ids: list[str] | None):
    """Restrict rows to managed warehouses; null warehouse_id excluded for managers."""
    if managed_wh_ids is None:
        return stmt
    if not managed_wh_ids:
        return stmt.where(func.false())
    return stmt.where(getattr(model, "warehouse_id").in_(managed_wh_ids))


def apply_sales_return_store_scope(stmt, store_ids: list[str] | None):
    """Scope sales returns via linked ``SalesInvoice.store_id`` (null-store fail-closed)."""
    if store_ids is None:
        return stmt
    stmt = stmt.join(
        m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id
    )
    if not store_ids:
        return stmt.where(m.SalesInvoice.id.is_(None))  # empty managed → no rows
    return stmt.where(m.SalesInvoice.store_id.in_(store_ids))


def apply_quotation_store_scope(
    stmt,
    *,
    managed_store_ids: list[str] | None,
    user_id: str | None,
    tenant_id: str,
    company_id: str | None = None,
):
    """Scope quotations via native ``store_id`` plus legacy conversion / own-draft fallbacks.

    Rows with ``store_id`` use direct managed-store filter. Legacy null-store rows keep
    own-draft + converted in-scope docs until backfilled (ADR-005 membership deferred).
    """
    if managed_store_ids is None:
        return stmt
    if not managed_store_ids:
        if user_id:
            return stmt.where(
                or_(
                    m.SalesQuotation.created_by == user_id,
                    m.SalesQuotation.store_id.is_(None),
                )
            )
        return stmt.where(m.SalesQuotation.id.is_(None))

    in_scope_order = select(m.SalesOrder.id).where(
        m.SalesOrder.tenant_id == tenant_id,
        m.SalesOrder.store_id.in_(managed_store_ids),
    )
    in_scope_inv = select(m.SalesInvoice.id).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.store_id.in_(managed_store_ids),
    )
    if company_id:
        in_scope_order = in_scope_order.where(m.SalesOrder.company_id == company_id)
        in_scope_inv = in_scope_inv.where(m.SalesInvoice.company_id == company_id)

    legacy_visible = or_(
        m.SalesQuotation.converted_order_id.in_(in_scope_order),
        m.SalesQuotation.converted_invoice_id.in_(in_scope_inv),
    )
    visible = or_(
        m.SalesQuotation.store_id.in_(managed_store_ids),
        legacy_visible,
    )
    if user_id:
        visible = or_(
            visible,
            and_(
                m.SalesQuotation.created_by == user_id,
                m.SalesQuotation.store_id.is_(None),
            ),
        )
    return stmt.where(visible)


async def assert_quotation_in_manager_scope(
    db: AsyncSession, claims: dict, quote: m.SalesQuotation
) -> None:
    """403 when quotation is outside managed store scope."""
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return

    sid = getattr(quote, "store_id", None)
    if sid:
        assert_store_in_manager_scope(managed, str(sid), allow_unset=False)
        return

    user_id = claims.get("sub")
    if user_id and quote.created_by == user_id:
        return
    if not managed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Quotation is outside your managed store scope.",
            },
        )
    if quote.converted_order_id:
        order = await db.get(m.SalesOrder, quote.converted_order_id)
        sid = getattr(order, "store_id", None) if order else None
        if sid and str(sid) in managed:
            return
    if quote.converted_invoice_id:
        inv = await db.get(m.SalesInvoice, quote.converted_invoice_id)
        sid = getattr(inv, "store_id", None) if inv else None
        if sid and str(sid) in managed:
            return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": "Quotation is outside your managed store scope.",
        },
    )


async def managed_liquid_account_ids(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_ids: list[str] | None,
    company_id: str | None = None,
) -> list[str] | None:
    """Liquid (cash/bank) account IDs touched by posted journals in scoped stores.

    Returns ``None`` when ``store_ids`` is ``None`` (tenant-wide). Empty list when
    no managed stores or no in-scope liquid activity.
    """
    if store_ids is None:
        return None
    if not store_ids:
        return []
    stmt = (
        select(m.JournalEntryLine.account_id)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntry.status == "posted",
            m.JournalEntry.store_id.in_(store_ids),
            or_(
                m.Account.is_cash_account.is_(True),
                m.Account.is_bank_account.is_(True),
            ),
        )
        .distinct()
    )
    if company_id:
        stmt = stmt.where(m.JournalEntry.company_id == company_id)
    return [
        str(aid)
        for aid in (await db.execute(stmt)).scalars().all()
        if aid
    ]


def assert_company_level_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot perform company-level writes.",
) -> None:
    """403 when store_manager attempts tenant/company-level configuration writes."""
    if managed_ids is None:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
        },
    )


def assert_company_level_accounting_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot perform company-level accounting writes.",
) -> None:
    """403 when store_manager attempts company-level chart/liquid account structure writes."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_fiscal_period_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company fiscal period status CSV.",
) -> None:
    """403 when store_manager exports fiscal period status CSV (company close state).

    GET fiscal-period status is separately denied; CSV dump is company-level
    administration (close already denied; reopen is admin-role gated).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_fiscal_period_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company fiscal period close status; "
        "scoped journal/report ops remain."
    ),
) -> None:
    """403 when store_manager reads fiscal period open/close status (company admin dump).

    Close/export already denied; GET dumped year bounds and ``current_period_closed``.
    Scoped journal/report ops remain (server-side open-period checks still apply).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_bank_feed_settings_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export bank-feed connector settings CSV.",
) -> None:
    """403 when store_manager exports bank-feed capability/settings CSV.

    GET ``/settings/bank-feed`` is separately denied; CSV dump is company-level
    administration (connection list/patch/sync on managed liquid accounts remain).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_bank_feed_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view bank-feed connector capability settings; "
        "managed bank connection ops remain."
    ),
) -> None:
    """403 when store_manager reads bank-feed capability/settings (infra config dump).

    CSV export already denied; GET dumped sync_enabled/providers/timeouts/celery
    interval. Scoped bank connection list/export/patch/sync remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_email_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view or export company email/SMTP settings; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /settings/email or /export.

    Tenant SMTP host/from/username status dump is company infra admin.
    PATCH/test remain admin-role gated; SMS/storage settings separate.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_sms_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view or export company SMS/Twilio settings; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /settings/sms or /export.

    Provider/capability status dump is company infra admin. Test send remains
    admin-role gated; storage settings separate.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_storage_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view or export company storage backend settings; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /settings/storage or /export.

    Storage backend/bucket capability dump is company infra admin.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_api_keys_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list or export company API keys; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /api-keys or /export.

    API key metadata/prefix dump is company security admin. Create/revoke/detail/
    usage remain admin-role gated for a later slice.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_webhooks_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list or export company webhooks; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /webhooks or /export.

    Endpoint URL/event subscription dump is company security admin.
    Deliveries use ``assert_company_level_webhook_deliveries_read_denied``.
    Create/patch/delete/test remain admin-role gated for a later slice.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_webhook_deliveries_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list or export company webhook deliveries; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads GET /webhooks/deliveries or /export.

    Delivery attempt history dump is company security admin. Endpoint
    list/export already denied; mutations remain admin-role gated.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_tax_rate_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company tax rates CSV.",
) -> None:
    """403 when store_manager exports tax rates CSV (company tax master dump).

    List GET is separately denied; store-scoped tax reports/filing remain. Full rate
    export is company-level administration (create/patch/default already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_tax_rate_list_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company tax rates; "
        "scoped tax reports/filing remain."
    ),
) -> None:
    """403 when store_manager lists company tax rates (master dump).

    Create/patch/default and CSV export already denied; GET ``/tax/rates`` dumped
    the full company rate table. Detail GET is separately denied. Store-scoped tax
    report/filing remain; ``/tax/calculate`` remains.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_tax_rate_detail_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company tax rate details; "
        "scoped tax reports/filing remain."
    ),
) -> None:
    """403 when store_manager reads a company tax rate by id (master dump).

    List GET/export/writes already denied; detail GET would bypass list deny via
    known ``rate_id``. Store-scoped tax report/filing remain; ``/tax/calculate``
    remains.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_settings_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update company-level settings.",
) -> None:
    """403 when store_manager attempts tenant/company settings writes (approval matrix, FX, FEFO)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_expense_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company expense approval settings; "
        "scoped expense ops remain."
    ),
) -> None:
    """403 when store_manager reads expense approval matrix (company admin dump).

    PATCH and CSV export already denied; GET dumped thresholds/levels/roles.
    Scoped expense create/approve/list remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_credit_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company early-pay credit settings; "
        "scoped credit AR/AP ops remain."
    ),
) -> None:
    """403 when store_manager reads company early-pay credit settings (admin dump).

    PATCH and CSV export already denied; GET dumped discount pct/days/enabled.
    Scoped credit aging/statements/payments remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_inventory_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company inventory FEFO settings; "
        "scoped warehouse stock ops remain."
    ),
) -> None:
    """403 when store_manager reads company FEFO inventory settings (admin dump).

    PATCH and CSV export already denied; GET dumped ``fefo_strict_warehouse``.
    Scoped warehouse stock-in/out and FEFO enforcement at write time remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_settings_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company-level settings CSVs.",
) -> None:
    """403 when store_manager exports company settings CSVs (approval/FX/FEFO/early-pay).

    Expense/credit/inventory settings GETs are separately denied. FX exchange-rates
    GET is separately denied. Full CSV dumps are company-level administration
    (writes already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_exchange_rates_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company exchange rates or FX provider settings; "
        "scoped credit ops remain."
    ),
) -> None:
    """403 when store_manager reads company FX rates + provider settings.

    Upsert/delete/refresh/settings PATCH and CSV export already denied; GET dumped
    base currency, ``fx_auto_refresh``, provider, and full rate table. Credit AR/AP
    ops remain store+WH scoped.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_purchasing_settings_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update company-level purchasing approval settings.",
) -> None:
    """403 when store_manager attempts purchasing PR approval matrix writes (company-level)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_purchasing_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company purchasing approval settings; "
        "scoped PR/PO ops remain."
    ),
) -> None:
    """403 when store_manager reads purchasing PR approval matrix (company admin dump).

    PATCH and CSV export already denied; GET dumped full levels/roles/thresholds.
    Scoped purchasing PR/PO/GRN ops remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_purchasing_settings_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company purchasing approval settings CSV.",
) -> None:
    """403 when store_manager exports purchasing PR approval settings CSV.

    GET settings is separately denied; matrix dump is company-level administration
    (PATCH already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_admin_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot perform company-level user/role administration.",
) -> None:
    """403 when store_manager attempts user/role management writes (users module)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_audit_cold_archive_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company-wide cold audit archives; "
        "use live audit-logs scoped to self and managed store/warehouse details."
    ),
) -> None:
    """403 when store_manager lists/exports cold audit archive manifests (tenant-wide packs)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_audit_chain_verify_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot verify the company-wide audit hash chain; "
        "use live audit-logs scoped to self and managed store/warehouse details."
    ),
) -> None:
    """403 when store_manager runs tenant-wide audit integrity verification.

    Live scoped ``/audit-logs`` list/export remain; full-chain verify is company
    compliance administration (cold archive list/export already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_audit_retention_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company audit retention policy; "
        "use live audit-logs scoped to self and managed store/warehouse details."
    ),
) -> None:
    """403 when store_manager reads audit retention policy (compliance admin dump).

    Cold archive list/export and hash-chain verify already denied; GET dumped
    retention years / purge_allowed. Live scoped ``/audit-logs`` list/export remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_membership_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot assign or revoke company memberships.",
) -> None:
    """403 when store_manager attempts company membership assign/revoke (companies module)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_membership_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company memberships; "
        "use users list/get for operational staff lookup."
    ),
) -> None:
    """403 when store_manager lists company user↔company memberships.

    Assign/revoke already denied; GET list was open when ``companies:read`` was
    over-granted and dumps the company membership graph. ``GET /users`` list/get remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_company_branding_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update company profile or branding.",
) -> None:
    """403 when store_manager attempts company profile/logo branding writes (companies module)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_company_profile_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company profile branding details; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager reads company profile (branding/legal dump).

    Profile/logo writes already denied; GET ``/companies/{id}`` dumped name/tax/address
    branding fields. Company logo binary GET remains for workspace chrome.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_company_profile_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot export company profile CSV; "
        "workspace switcher + logo binary GET remain for chrome."
    ),
) -> None:
    """403 when store_manager exports company profile CSV (legal/tax/branding dump).

    Company list/detail GET + ``/me``/``/workspace`` profile fields already denied or
    redacted; ``GET /tenants/me/export`` dumped the same company profile pack.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_tenant_me_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot read GET /tenants/me company/tenant profile; "
        "workspace switcher + logo binary GET remain for chrome."
    ),
) -> None:
    """403 when store_manager reads GET /tenants/me (tenant+company profile dump).

    Company list/detail GET + profile CSV export already denied or redacted;
    ``GET /tenants/me`` serializes the same legal/tax/branding/document pack.
    Logo binary GET + ``/me`` + ``/workspace`` switcher-only remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)



def assert_company_level_company_list_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company profiles (branding/legal dump); "
        "workspace switcher + managed store ops remain."
    ),
) -> None:
    """403 when store_manager lists companies (same profile dump as detail GET).

    ``GET /companies`` returned full ``serialize_company`` rows after detail GET was
    denied. Workspace ``/me`` + ``/workspace`` remain with switcher-only company
    fields (legal/tax/address/store_limit + company_entitlement redacted).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def omit_company_profile_details(managed_ids: list[str] | None) -> bool:
    """True when store_manager session payloads must omit full company profiles.

    Detail/list company GETs already denied; ``GET /me`` and ``GET /workspace``
    must not re-dump legal/tax/address/store_limit via ``serialize_company``.
    Switcher chrome fields (id/name/has_logo/industry) remain.
    """
    return managed_ids is not None


def omit_company_entitlement(managed_ids: list[str] | None) -> bool:
    """True when store_manager must omit tenant company-entitlement subscription dump.

    ``company_entitlement`` on ``/me`` + ``/workspace`` exposed max_companies /
    over_entitlement capacity (admin subscription surface). Store ops remain.
    """
    return managed_ids is not None


def assert_company_level_document_settings_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update company document numbering or print templates.",
) -> None:
    """403 when store_manager attempts document numbering / print template writes (tenants module)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_document_settings_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot export company document numbering or print template settings; "
        "admin export remains."
    ),
) -> None:
    """403 when store_manager exports document settings CSV (numbering/print-template dump).

    PATCH writes already denied; ``GET /tenants/me/document-settings/export`` dumped
    company document numbering + print templates. Logo binary GET remains for chrome.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_print_templates_preview_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot preview company print templates; "
        "document numbering/print writes + CSV export already denied."
    ),
) -> None:
    """403 when store_manager previews company print templates.

    Document settings write/export already denied; GET
    ``/tenants/me/print-templates/preview`` dumped invoice/receipt
    branding samples. Operational document print paths remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)



def assert_company_level_tenant_profile_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update tenant company profile settings.",
) -> None:
    """403 when store_manager attempts ``PATCH /tenants/me`` (company-level tenant profile)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_onboarding_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot access the company onboarding checklist; "
        "tenant bootstrap progress is company-admin only."
    ),
) -> None:
    """403 when store_manager reads tenant onboarding checklist (company bootstrap).

    Checklist export/skip/dismiss already admin-role gated; GET was open via
    ``current_claims`` and dumps company setup progress.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_onboarding_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot export company onboarding checklist CSV; "
        "checklist GET already denied."
    ),
) -> None:
    """403 when store_manager exports onboarding checklist CSV (company bootstrap dump).

    Checklist GET already denied; ``GET /onboarding/checklist/export`` dumped the same
    tenant bootstrap progress pack. Skip/dismiss remain admin-gated.
    """
    assert_company_level_write_denied(managed_ids, message=message)



def assert_company_level_business_types_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list business types; "
        "company create/bootstrap catalogs are company-admin only."
    ),
) -> None:
    """403 when store_manager lists business-type catalog (company create bootstrap).

    ``POST /companies`` already denied; GET ``/business-types`` was open via
    ``current_claims`` as the industry picker for company creation.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_store_limit_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot allocate company store entitlement limits.",
) -> None:
    """403 when store_manager attempts tenant store-limit allocation (companies module)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_store_entitlement_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company store entitlement allocations; "
        "subscription capacity is company/tenant-admin only."
    ),
) -> None:
    """403 when store_manager reads company store-entitlement (subscription capacity dump).

    ``PATCH /companies/{id}/store-limit`` already denied; GET was open via ``stores:read``
    and dumps company plan/allocation. Managed store list/ops remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_legacy_transaction_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot use legacy unscoped sale/purchase transactions.",
) -> None:
    """403 when store_manager lists or posts legacy ``/sales`` or ``/purchases`` (no store_id).

    Modern sales invoices and purchasing PR/PO/GRN paths remain available when
    store/warehouse scoped.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_org_create_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create company-level org structures.",
) -> None:
    """403 when store_manager attempts tenant/company org creates (companies, warehouses)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_store_manager_assignment_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_manager: bool,
    message: str = "Store managers cannot assign or clear store managers.",
) -> None:
    """403 when store_manager attempts company-level store manager_id assignment."""
    if not changing_manager:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_store_branch_assignment_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_branch: bool,
    message: str = "Store managers cannot assign or clear store branch org links.",
) -> None:
    """403 when store_manager attempts company-level store↔branch org assignment.

    Branch/department master writes are already denied; store ``branch_id`` /
    ``clear_branch`` is the same company-level org graph and stays admin-only.
    """
    if not changing_branch:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_expense_department_assignment_write_denied(
    managed_ids: list[str] | None,
    *,
    department_id: str | None = None,
    clear_department: bool = False,
    message: str = "Store managers cannot assign or clear expense department org links.",
) -> None:
    """403 when store_manager attempts company-level expense↔department org assignment.

    Department master writes are already denied; ``department_id`` / ``clear_department``
    on expense create/patch/recurring-create is the same company-level org graph.
    """
    if managed_ids is None:
        return
    changing = bool(clear_department) or bool((department_id or "").strip())
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_expense_store_clear_write_denied(
    managed_ids: list[str] | None,
    *,
    clear_store: bool,
    message: str = "Store managers cannot clear expense store assignment.",
) -> None:
    """403 when store_manager clears expense.store_id (company null-store escape)."""
    if not clear_store:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_warehouse_manager_assignment_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_manager: bool,
    message: str = "Store managers cannot assign or clear warehouse managers.",
) -> None:
    """403 when store_manager attempts company-level warehouse manager_id assignment.

    Warehouse create is already denied; ``manager_id`` / ``clear_manager`` on
    managed warehouses stays admin-only (same org-assignment class as stores).
    """
    if not changing_manager:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_warehouse_store_assignment_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_store: bool,
    message: str = "Store managers cannot assign or clear warehouse store links.",
) -> None:
    """403 when store_manager attempts company-level warehouse↔store org assignment.

    Warehouse create is already denied; ``store_id`` / ``clear_store`` re-homes
    inventory scope across the company org graph and stays admin-only.
    """
    if not changing_store:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_warehouse_structure_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_structure: bool,
    message: str = "Store managers cannot change warehouse type or capacity.",
) -> None:
    """403 when store_manager attempts company-level warehouse structural fields.

    ``warehouse_type`` / ``capacity`` are company inventory-master attributes;
    name/address on managed warehouses remain allowed (``is_active`` is lifecycle).
    """
    if not changing_structure:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_warehouse_lifecycle_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_active: bool,
    message: str = "Store managers cannot activate or deactivate warehouses.",
) -> None:
    """403 when store_manager attempts company-level warehouse is_active lifecycle.

    Warehouse create is already denied; soft activate/deactivate stays admin-only.
    Name/address patches on managed warehouses remain allowed.
    """
    if not changing_active:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_store_lifecycle_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_active: bool,
    message: str = "Store managers cannot activate or deactivate stores.",
) -> None:
    """403 when store_manager attempts company-level store is_active lifecycle.

    Store create is already denied; soft activate/deactivate (entitlement-gated)
    stays admin-only. Name/phone/address/operating_hours on managed stores remain.
    """
    if not changing_active:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_pos_hold_expire_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot run POS hold expire-stale maintenance.",
) -> None:
    """403 when store_manager hits company POS hold expire-stale maintenance.

    List/create/resume already auto-expire the caller's own soft-reserves.
    Explicit ``POST /pos/holds/expire-stale`` stays admin/cashier maintenance
    (cashiers keep self-expire; store_manager view is company-ops denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_liquid_account_lifecycle_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_active: bool,
    message: str = "Store managers cannot activate or deactivate liquid accounts.",
) -> None:
    """403 when store_manager attempts company-level liquid account is_active lifecycle.

    Liquid account create is already denied; soft activate/deactivate stays
    admin-only. Name patches on managed liquid accounts remain; bank identity
    fields use ``assert_liquid_account_bank_details_write_denied``.
    """
    if not changing_active:
        return
    assert_company_level_write_denied(managed_ids, message=message)


LIQUID_ACCOUNT_BANK_DETAIL_FIELDS = frozenset(
    {
        "bank_name",
        "account_number",
        "bank_branch",
        "clear_bank_details",
    }
)


def assert_liquid_account_bank_details_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot update liquid account bank details.",
) -> None:
    """403 when store_manager patches bank identity fields on liquid accounts.

    ``name`` on managed liquid accounts remains allowed; create / ``is_active``
    lifecycle stay company-level denied separately.
    """
    if managed_ids is None:
        return
    fields = sorted(k for k in LIQUID_ACCOUNT_BANK_DETAIL_FIELDS if k in payload)
    if not fields:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
            "fields": fields,
        },
    )


def assert_company_level_bank_connection_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or delete bank feed connections.",
) -> None:
    """403 when store_manager creates/deletes bank feed connections (credentials).

    List/export/patch/sync on managed liquid-account connections remain scoped.
    Credential field patches use ``assert_bank_connection_credentials_write_denied``.
    Soft ``is_active`` uses ``assert_bank_connection_lifecycle_write_denied``.
    """
    assert_company_level_write_denied(managed_ids, message=message)


BANK_CONNECTION_CREDENTIAL_FIELDS = frozenset(
    {
        "provider",
        "external_account_id",
        "feed_url",
        "access_token",
        "clear_credentials",
    }
)


def assert_bank_connection_credentials_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot update bank feed credentials.",
) -> None:
    """403 when store_manager patches bank-feed credential / identity fields.

    ``display_name`` on managed connections remains. Sync policy fields use
    ``assert_bank_connection_sync_policy_write_denied``. ``is_active`` is gated
    by ``assert_bank_connection_lifecycle_write_denied``.
    """
    if managed_ids is None:
        return
    fields = sorted(k for k in BANK_CONNECTION_CREDENTIAL_FIELDS if k in payload)
    if not fields:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
            "fields": fields,
        },
    )


BANK_CONNECTION_SYNC_POLICY_FIELDS = frozenset(
    {
        "auto_sync",
        "auto_match_after_sync",
        "sync_lookback_days",
    }
)


def assert_bank_connection_sync_policy_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot update bank feed sync policy.",
) -> None:
    """403 when store_manager patches bank-feed auto-sync / lookback policy.

    ``display_name`` and manual ``/sync`` on managed connections remain;
    credentials and ``is_active`` stay company-level denied separately.
    """
    if managed_ids is None:
        return
    fields = sorted(k for k in BANK_CONNECTION_SYNC_POLICY_FIELDS if k in payload)
    if not fields:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
            "fields": fields,
        },
    )


def assert_bank_connection_lifecycle_write_denied(
    managed_ids: list[str] | None,
    *,
    changing_active: bool,
    message: str = "Store managers cannot activate or deactivate bank connections.",
) -> None:
    """403 when store_manager attempts company-level bank connection is_active lifecycle.

    Connection create/delete already denied; soft activate/deactivate stays
    admin-only. Display name patches on managed connections remain; sync policy
    uses ``assert_bank_connection_sync_policy_write_denied``.
    """
    if not changing_active:
        return
    assert_company_level_write_denied(managed_ids, message=message)



async def assert_products_in_manager_warehouse_scope(
    db: AsyncSession,
    tenant_id: str,
    managed_wh_ids: list[str] | None,
    product_ids: list[str],
    *,
    company_id: str | None = None,
    message: str = "Product is outside your managed warehouse scope for label printing.",
) -> None:
    """403 when store_manager targets products without managed-warehouse stock rows.

    Empty managed warehouse set fail-closes. Tenant-wide (``None``) skips.
    """
    if managed_wh_ids is None:
        return
    pids = [str(p).strip() for p in product_ids if str(p or "").strip()]
    if not pids:
        return
    if not managed_wh_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": message,
            },
        )
    stmt = (
        select(m.WarehouseStock.product_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            m.WarehouseStock.warehouse_id.in_(managed_wh_ids),
            m.WarehouseStock.product_id.in_(pids),
        )
        .distinct()
    )
    if company_id:
        stmt = stmt.where(m.WarehouseStock.company_id == company_id)
    allowed = {str(pid) for pid in (await db.execute(stmt)).scalars().all() if pid}
    missing = [pid for pid in pids if pid not in allowed]
    if missing:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": message,
                "product_ids": missing,
            },
        )


def assert_company_level_org_unit_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or update branches or departments.",
) -> None:
    """403 when store_manager attempts branch/department org-unit writes (company-level)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_org_unit_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company branch/department CSVs.",
) -> None:
    """403 when store_manager exports branches/departments CSV (company org master dump).

    List GETs also denied; full org-unit export is company-level administration
    (writes already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_org_unit_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company branches or departments; "
        "managed store ops remain."
    ),
) -> None:
    """403 when store_manager lists branches/departments (company org-unit dump).

    Create/patch + CSV export already denied; ``GET /branches`` and ``GET /departments``
    dumped full org charts. Store/expense UIs soft-fail empty lists.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_expense_category_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or update expense categories or budget limits.",
) -> None:
    """403 when store_manager attempts expense category master writes (incl. budget limits)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_expense_category_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company expense categories CSV.",
) -> None:
    """403 when store_manager exports expense categories CSV (company finance master dump).

    List GET also denied; full category export is company-level administration
    (writes already denied). Spend/pending variance via budgets remains scoped.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_expense_category_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company expense categories; "
        "scoped spend/pending variance via budgets remain."
    ),
) -> None:
    """403 when store_manager lists expense categories (company budget master dump).

    Create/patch + CSV export already denied; ``GET /expenses/categories`` dumped
    budget_amount / approval matrix fields. Expense UI soft-fails empty lists;
    ``/expenses/budgets`` spend/pending remains store-scoped.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_catalog_meta_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or update catalog categories, brands, or units.",
) -> None:
    """403 when store_manager attempts company-level catalog meta writes (categories/brands/units)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_catalog_meta_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company catalog meta CSVs.",
) -> None:
    """403 when store_manager exports categories/brands/units CSV (company catalog dump).

    List GETs also denied; full meta export is company-level administration
    (writes already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_catalog_meta_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company catalog categories, brands, or units; "
        "managed WH stock ops + product reads remain."
    ),
) -> None:
    """403 when store_manager lists catalog categories/brands/units (company meta dump).

    Create/patch/deactivate + CSV export already denied; ``GET /catalog/categories``,
    ``GET /catalog/brands``, and ``GET /catalog/units`` dumped full catalog masters.
    Brand logo binary GET + units/convert remain; inventory UIs soft-fail empty lists.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_customer_group_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or update customer groups.",
) -> None:
    """403 when store_manager attempts company-level customer group master writes."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_customer_group_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company customer groups CSV.",
) -> None:
    """403 when store_manager exports customer groups CSV (company sales master dump).

    List/get already denied alongside create/patch/deactivate and party↔group assignment.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_customer_group_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view the company customer groups catalog; "
        "customer list/get and sales ops remain."
    ),
) -> None:
    """403 when store_manager lists/gets customer groups (company sales-master catalog).

    Create/patch/deactivate/export and party↔group assignment already denied; GET list/detail
    was a leftover company dump. Customer list/get + name patches remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_customer_group_assignment_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot assign or clear customer groups on parties.",
) -> None:
    """403 when store_manager sets customer_group_id / customer_group on a party.

    Customer group master CRUD is already denied; party↔group assignment is the
    same company sales-master graph and stays admin-only. Name party
    patches remain (phone/email/address/notes gated separately).
    """
    if managed_ids is None:
        return
    changing = "customer_group_id" in payload or "customer_group" in payload
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_classification_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party category or party_type.",
) -> None:
    """403 when store_manager sets party category / party_type (company classification).

    Name remains. On create full dumps, only non-empty values
    deny (``clear_counts=False``). On PATCH exclude_unset, present keys deny
    including explicit null clears (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    if clear_counts:
        changing = "category" in payload or "party_type" in payload
    else:
        cat = payload.get("category")
        ptype = payload.get("party_type")
        changing = (
            cat is not None and str(cat).strip() != ""
        ) or (
            ptype is not None and str(ptype).strip() != ""
        )
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_code_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party master codes.",
) -> None:
    """403 when store_manager sets customer/supplier ``code`` (company party master).

    Name remains. Create without a code still allowed
    (``clear_counts=False`` ignores empty/null). PATCH present ``code`` key
    denies including clears (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    if clear_counts:
        changing = "code" in payload
    else:
        code = payload.get("code")
        changing = code is not None and str(code).strip() != ""
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_email_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party master emails.",
) -> None:
    """403 when store_manager sets customer/supplier ``email`` (company contact master).

    Nested contact create/delete is already denied; primary party email is the
    same company CRM identity surface. Name remains (phone/address/notes gated).
    Create without email still allowed (``clear_counts=False``). PATCH present
    ``email`` denies including clears (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    if clear_counts:
        changing = "email" in payload
    else:
        email = payload.get("email")
        changing = email is not None and str(email).strip() != ""
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_phone_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party master phones.",
) -> None:
    """403 when store_manager sets customer/supplier ``phone`` (company contact master).

    Nested contact create/delete and primary email are already denied; primary
    party phone is the same company CRM identity surface. Name remains
    (address/geo/notes gated separately). Create without phone still allowed
    (``clear_counts=False``). PATCH present ``phone`` denies including clears
    (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    if clear_counts:
        changing = "phone" in payload
    else:
        phone = payload.get("phone")
        changing = phone is not None and str(phone).strip() != ""
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_address_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party master address or geo.",
) -> None:
    """403 when store_manager sets customer/supplier address/lat/long (company CRM).

    Email/phone/contacts are already denied; primary address and coordinates are
    the same company party-location master surface. Name remains (notes gated
    separately). Create without address still allowed (``clear_counts=False``).
    PATCH present ``address`` / ``latitude`` / ``longitude`` denies including
    clears (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    keys = ("address", "latitude", "longitude")
    if clear_counts:
        changing = any(k in payload for k in keys)
    else:
        changing = False
        for k in keys:
            val = payload.get(k)
            if val is None:
                continue
            if isinstance(val, str) and str(val).strip() == "":
                continue
            changing = True
            break
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_notes_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    clear_counts: bool = False,
    message: str = "Store managers cannot set party master notes.",
) -> None:
    """403 when store_manager sets customer/supplier ``notes`` (company CRM memo).

    Email/phone/address/contacts are already denied; free-text notes are the
    same company party-master annotation surface. Name remains. Create without
    notes still allowed (``clear_counts=False``). PATCH present ``notes`` denies
    including clears (``clear_counts=True``).
    """
    if managed_ids is None:
        return
    if clear_counts:
        changing = "notes" in payload
    else:
        notes = payload.get("notes")
        changing = notes is not None and str(notes).strip() != ""
    if not changing:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_party_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company party master CSVs.",
) -> None:
    """403 when store_manager exports customers/suppliers CSV (company CRM dump).

    List/get and scoped party history (+ CSV) remain; full master export is
    company-level PII (email/phone/address/notes already gated on writes).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_user_admin_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot export company user/role administration CSVs."
    ),
) -> None:
    """403 when store_manager exports users/roles/permissions matrix CSVs.

    ``GET /users`` list/get remain with permission matrices redacted; roles catalog/detail
    are separately denied. Full roster and matrix dumps are company-level admin surfaces
    (writes already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def omit_user_permission_matrix(managed_ids: list[str] | None) -> bool:
    """True when store_manager users list/get must omit permission maps.

    Roles catalog/detail already denied; returning full ``permissions`` on
    ``GET /users`` would re-expose the same company permission matrix. Staff
    identity fields (email/name/role/active) remain for operational lookup.
    """
    return managed_ids is not None


def assert_company_level_roles_catalog_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view the company roles catalog or role permission details; "
        "use users list/get for operational staff lookup."
    ),
) -> None:
    """403 when store_manager reads roles catalog or role detail (permission matrix dump).

    ``GET /users`` list/get remain with permission matrices redacted; roles CSV /
    permissions-matrix CSV already denied; role create/patch/delete already denied.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_user_stats_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company-wide user/role dashboard KPIs; "
        "use list/get for users."
    ),
) -> None:
    """403 when store_manager reads tenant-wide dashboard user-stats KPIs.

    Dedicated ``/dashboard/user-stats`` (+ export) and main-dashboard
    ``user_stats`` embed are company-admin surfaces; ``GET /users`` list/get remain
    with permission matrices redacted (roles catalog/detail separately denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_product_import_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot bulk-import company catalog products.",
) -> None:
    """403 when store_manager attempts company-level product CSV import (catalog master)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_product_master_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or update company catalog products.",
) -> None:
    """403 when store_manager attempts product master writes (create/patch/variants/images/barcode)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_product_variants_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company product variants CSV.",
) -> None:
    """403 when store_manager exports company-wide product variants CSV (catalog master dump).

    Per-product variants list/get and WH-scoped products export remain; full variants roster
    export is company-level administration (variant writes already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_product_images_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company product images CSV.",
) -> None:
    """403 when store_manager exports product images metadata CSV (catalog master dump).

    Per-product images list/get remain; CSV dump is company-level administration
    (image upload/patch/delete already denied).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_stock_import_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot bulk-import stock across company warehouses.",
) -> None:
    """403 when store_manager attempts company-level stock CSV import (any warehouse / product.stock_qty)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_opening_stock_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot record opening stock (company fiscal inventory init).",
) -> None:
    """403 when store_manager attempts opening-stock fiscal init (BR-5.2).

    Day-to-day stock-in/out on managed warehouses remain allowed; opening stock is
    company inventory-master / fiscal-start seeding (alongside stock CSV import deny).
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_ai_report_template_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot create or delete company AI report templates.",
) -> None:
    """403 when store_manager attempts company-level AI report template create/delete."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_ai_report_template_export_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot export company AI report templates CSV.",
) -> None:
    """403 when store_manager exports AI report templates CSV (company NL template dump).

    Template list/create/delete and NL generate already denied; CSV dump is the same
    company-level administration surface.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_ai_report_template_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company AI report templates; "
        "NL report generation is company-admin only."
    ),
) -> None:
    """403 when store_manager lists AI report templates (company NL template catalog).

    Create/delete/export and ``/ai/reports/generate`` already denied; GET list was a
    leftover company dump. Store-scoped ``/reports/*`` + Layer-1 AI remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_ai_report_generate_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot run company-level AI NL report generation.",
) -> None:
    """403 when store_manager attempts company-wide AI NL report generate/export.

    Store-scoped ``/reports/*`` and Layer-1 AI insights remain available.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_report_schedule_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot manage company report schedules.",
) -> None:
    """403 when store_manager attempts company-level report schedule CRUD/run.

    Store-scoped ``/reports/*`` reads remain available; schedule list/export
    use ``assert_company_level_report_schedule_read_denied``.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_report_schedule_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list or export company report email schedules; "
        "store-scoped /reports/* reads remain."
    ),
) -> None:
    """403 when store_manager reads GET /reports/schedules or /export.

    Writes already denied; schedule list/export dump company email cadence +
    recipients. Store-scoped report tabs remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_reports_exportable_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot list company exportable report catalogs; "
        "scoped /reports/* exports remain."
    ),
) -> None:
    """403 when store_manager reads GET /reports/exportable (company report catalog).

    Report schedule writes already denied; exportable dumped the full EXPORTABLE
    type/format catalog. Store-scoped report generation/export paths remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_bi_settings_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot update company business-insights settings.",
) -> None:
    """403 when store_manager attempts company-level BI settings writes (thresholds/formulas)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_bi_settings_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company business-insights settings; "
        "scoped overview/history/acknowledge/dismiss remain."
    ),
) -> None:
    """403 when store_manager reads company BI thresholds/settings (admin dump).

    PUT already denied; GET dumped slow_moving_days/health_weights and related
    thresholds. Scoped BI overview/history/acknowledge/dismiss remain; static
    ``/formulas`` docs separately denied.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_company_level_bi_formulas_read_denied(
    managed_ids: list[str] | None,
    *,
    message: str = (
        "Store managers cannot view company business-insights formula docs; "
        "scoped overview/history/acknowledge/dismiss remain."
    ),
) -> None:
    """403 when store_manager reads company BI formula documentation dump.

    Settings GET/PUT already denied; GET ``/business-insights/formulas`` exposed
    Layer-1 formula catalog / threshold semantics. Scoped BI overview/history/
    acknowledge/dismiss remain.
    """
    assert_company_level_write_denied(managed_ids, message=message)


async def assert_bi_insight_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    insight: m.BusinessInsight,
) -> None:
    """403 when store_manager acknowledges/dismisses BI insight outside managed scope."""
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    if not managed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Business insight is outside your managed store scope.",
            },
        )

    tenant_id = claims["tenant_id"]
    company_id = claims.get("company_id")
    et = (insight.related_entity_type or "").strip().lower()
    eid = (insight.related_entity_id or "").strip()

    if et == "store":
        assert_store_in_manager_scope(managed, eid or None, allow_unset=False)
        return

    if et == "product" and eid:
        managed_wh = await managed_warehouse_ids(db, claims)
        await assert_products_in_manager_warehouse_scope(
            db,
            tenant_id,
            managed_wh,
            [eid],
            company_id=company_id,
            message="Business insight product is outside your managed warehouse scope.",
        )
        return

    if et == "customer" and eid:
        stmt = (
            select(m.SalesInvoice.id)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.customer_id == eid,
                m.SalesInvoice.store_id.in_(managed),
            )
            .limit(1)
        )
        if company_id:
            stmt = stmt.where(m.SalesInvoice.company_id == company_id)
        if (await db.execute(stmt)).scalar_one_or_none():
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Business insight customer is outside your managed store scope.",
            },
        )

    if et == "supplier" and eid:
        managed_wh = await managed_warehouse_ids(db, claims)
        if not managed_wh:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "STORE_SCOPE_DENIED",
                    "message": "Business insight supplier is outside your managed warehouse scope.",
                },
            )
        wh_expr = func.coalesce(
            m.PurchaseInvoice.warehouse_id,
            m.GoodsReceipt.warehouse_id,
            m.PurchaseOrder.warehouse_id,
        )
        stmt = (
            select(m.PurchaseInvoice.id)
            .outerjoin(
                m.GoodsReceipt, m.GoodsReceipt.id == m.PurchaseInvoice.goods_receipt_id
            )
            .outerjoin(
                m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseInvoice.purchase_order_id
            )
            .where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.supplier_id == eid,
                wh_expr.in_(managed_wh),
            )
            .limit(1)
        )
        if company_id:
            stmt = stmt.where(m.PurchaseInvoice.company_id == company_id)
        if (await db.execute(stmt)).scalar_one_or_none():
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Business insight supplier is outside your managed warehouse scope.",
            },
        )

    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": "Business insight is outside your managed store scope.",
            "related_entity_type": et or None,
        },
    )


def assert_party_master_deactivate_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot deactivate customers or suppliers.",
) -> None:
    """403 when store_manager attempts company-level party deactivate (customer/supplier DELETE)."""
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_status_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot change customer or supplier status.",
) -> None:
    """403 when store_manager patches party ``status`` (activate/deactivate lifecycle).

    DELETE deactivate is already denied; PATCH ``status`` must not bypass that
    company party-master gate. Name remains (phone/email/address/notes gated).
    """
    if managed_ids is None:
        return
    if "status" not in payload:
        return
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_master_contact_write_denied(
    managed_ids: list[str] | None,
    *,
    message: str = "Store managers cannot add or remove party contacts.",
) -> None:
    """403 when store_manager attempts company-level party contact create/delete.

    Nested ``contacts`` on customer/supplier create use
    ``assert_party_nested_contacts_create_denied``; dedicated ``/contacts``
    POST/DELETE endpoints are the same company-level master surface.
    """
    assert_company_level_write_denied(managed_ids, message=message)


def assert_party_nested_contacts_create_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    message: str = "Store managers cannot attach party contacts on create.",
) -> None:
    """403 when store_manager supplies ``contacts`` on customer/supplier create.

    Dedicated ``/contacts`` POST/DELETE are already denied; nested create must
    not bypass that company party-contact master gate. Name-only party create
    remains allowed.
    """
    if managed_ids is None:
        return
    contacts = payload.get("contacts")
    if not contacts:
        return
    if isinstance(contacts, list) and len(contacts) == 0:
        return
    assert_company_level_write_denied(managed_ids, message=message)


PARTY_CREDIT_MASTER_FIELDS = frozenset(
    {
        "credit_limit",
        "early_pay_discount_pct",
        "early_pay_discount_days",
        "payment_terms_days",
    }
)


def assert_party_credit_master_write_denied(
    managed_ids: list[str] | None,
    payload: dict,
    *,
    allow_zero_credit_limit: bool = False,
    allow_zero_payment_terms: bool = False,
    message: str = (
        "Store managers cannot update party credit limits, payment terms, "
        "or early-payment discounts."
    ),
) -> None:
    """403 when store_manager attempts party-level credit/payment-terms master writes."""
    if managed_ids is None:
        return
    fields: set[str] = set()
    if "credit_limit" in payload:
        val = payload.get("credit_limit")
        if not (allow_zero_credit_limit and (val is None or float(val or 0) == 0)):
            fields.add("credit_limit")
    if "payment_terms_days" in payload:
        val = payload.get("payment_terms_days")
        if not (allow_zero_payment_terms and (val is None or int(val or 0) == 0)):
            fields.add("payment_terms_days")
    for key in ("early_pay_discount_pct", "early_pay_discount_days"):
        if key in payload and payload.get(key) is not None:
            fields.add(key)
    if not fields:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
            "fields": sorted(fields),
        },
    )


def assert_credit_limit_override_denied(
    managed_ids: list[str] | None,
    *,
    override: bool,
    message: str = "Store managers cannot override customer credit limits.",
) -> None:
    """403 when store_manager attempts credit_limit_override on invoice post / POS credit.

    Default role includes ``credit:approve``; override remains company/finance admin.
    """
    if managed_ids is None or not override:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": message,
        },
    )


async def assert_liquid_account_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    store_ids: list[str] | None,
    *,
    company_id: str | None = None,
) -> None:
    """403 when a store_manager reads a liquid account outside managed-store journals."""
    if store_ids is None:
        return
    allowed = await managed_liquid_account_ids(
        db, tenant_id, store_ids=store_ids, company_id=company_id
    )
    aid = (account_id or "").strip()
    if not allowed or aid not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Bank/cash account is outside your managed store scope.",
                "account_id": aid or None,
            },
        )


async def assert_optional_liquid_account_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    liquid_account_id: str | None,
    store_ids: list[str] | None,
    *,
    company_id: str | None = None,
) -> None:
    """403 when store_manager supplies ``liquid_account_id`` outside managed stores."""
    aid = (liquid_account_id or "").strip()
    if store_ids is None or not aid:
        return
    await assert_liquid_account_in_manager_scope(
        db, tenant_id, aid, store_ids, company_id=company_id
    )


async def _posted_journal_store_ids_for_account(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    *,
    company_id: str | None = None,
) -> list[str | None]:
    """Distinct journal store_ids with posted activity on one COA account."""
    aid = (account_id or "").strip()
    if not aid:
        return []
    stmt = (
        select(m.JournalEntry.store_id)
        .join(
            m.JournalEntryLine,
            m.JournalEntryLine.journal_entry_id == m.JournalEntry.id,
        )
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntryLine.account_id == aid,
            m.JournalEntry.status == "posted",
        )
        .distinct()
    )
    if company_id:
        stmt = stmt.where(m.JournalEntry.company_id == company_id)
    return list((await db.execute(stmt)).scalars().all())


def _liquid_account_has_managed_journal_activity(
    activity_stores: list[str | None],
    store_ids: list[str],
) -> bool:
    managed_set = set(store_ids)
    return any(sid is not None and str(sid) in managed_set for sid in activity_stores)


async def _coa_account_readable_by_manager(
    db: AsyncSession,
    tenant_id: str,
    account: m.Account,
    store_ids: list[str],
    *,
    company_id: str | None = None,
) -> bool:
    """True when store_manager may read one COA account (liquid-only; first-touch allowed)."""
    if not (account.is_cash_account or account.is_bank_account):
        return False
    allowed_liquid = await managed_liquid_account_ids(
        db, tenant_id, store_ids=store_ids, company_id=company_id
    )
    if allowed_liquid and account.id in allowed_liquid:
        return True
    activity_stores = await _posted_journal_store_ids_for_account(
        db, tenant_id, account.id, company_id=company_id
    )
    if not activity_stores:
        return True
    return _liquid_account_has_managed_journal_activity(activity_stores, store_ids)


async def assert_coa_account_read_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    account: m.Account,
    store_ids: list[str] | None,
    *,
    company_id: str | None = None,
) -> None:
    """403 when store_manager reads COA outside allowed liquid scope.

    Non-cash/bank accounts are company-level chart structure (denied). Liquid accounts
    with no prior journal activity are allowed (first-touch). Accounts with only
    foreign-store liquid activity are fail-closed.
    """
    if store_ids is None:
        return
    if company_id and account.company_id and str(account.company_id) != str(company_id):
        return
    aid = account.id
    if not (account.is_cash_account or account.is_bank_account):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": (
                    "Store managers cannot read non-cash/bank chart-of-accounts entries."
                ),
                "account_id": aid or None,
            },
        )
    if await _coa_account_readable_by_manager(
        db, tenant_id, account, store_ids, company_id=company_id
    ):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": (
                "Bank/cash account has activity only outside your managed store scope."
            ),
            "account_id": aid or None,
        },
    )


async def filter_coa_accounts_for_manager_read(
    db: AsyncSession,
    tenant_id: str,
    accounts: list[m.Account],
    store_ids: list[str] | None,
    *,
    company_id: str | None = None,
) -> list[m.Account]:
    """Return COA rows readable by store_manager (liquid-only; first-touch allowed)."""
    if store_ids is None:
        return accounts
    readable: list[m.Account] = []
    for account in accounts:
        if await _coa_account_readable_by_manager(
            db, tenant_id, account, store_ids, company_id=company_id
        ):
            readable.append(account)
    return readable


async def assert_opening_balance_account_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    store_ids: list[str] | None,
    *,
    company_id: str | None = None,
) -> None:
    """403 when store_manager posts opening balance outside allowed liquid scope.

    Non-cash/bank COA accounts are company-level structure (denied). Cash/bank with
    no prior journal activity is allowed (first-touch opening balance). Accounts with
    only foreign-store liquid activity are fail-closed.
    """
    if store_ids is None:
        return
    aid = (account_id or "").strip()
    account = await db.get(m.Account, aid)
    if not account or account.tenant_id != tenant_id:
        return
    if company_id and account.company_id and str(account.company_id) != str(company_id):
        return
    if not (account.is_cash_account or account.is_bank_account):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": (
                    "Store managers cannot post opening balances on non-cash/bank accounts."
                ),
                "account_id": aid or None,
            },
        )
    activity_stores = await _posted_journal_store_ids_for_account(
        db, tenant_id, aid, company_id=company_id
    )
    if not activity_stores:
        return
    if _liquid_account_has_managed_journal_activity(activity_stores, store_ids):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": (
                "Bank/cash account has activity only outside your managed store scope."
            ),
            "account_id": aid or None,
        },
    )


async def assert_sales_return_in_manager_scope(
    db: AsyncSession, claims: dict, sales_return: m.SalesReturn
) -> None:
    """403 when return's invoice store is outside managed scope."""
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    inv = await db.get(m.SalesInvoice, sales_return.sales_invoice_id)
    sid = getattr(inv, "store_id", None) if inv else None
    assert_store_in_manager_scope(managed, sid, allow_unset=False)


def apply_purchase_invoice_warehouse_scope(stmt, managed_wh_ids: list[str] | None):
    """Scope purchase invoices via direct warehouse_id, else linked GRN/PO warehouse.

    Prefer ``PurchaseInvoice.warehouse_id``, then GRN, then PO. Unlinked invoices with
    null warehouse remain fail-closed for store_managers.
    """
    if managed_wh_ids is None:
        return stmt
    if not managed_wh_ids:
        return stmt.where(func.false())
    stmt = stmt.outerjoin(
        m.GoodsReceipt, m.GoodsReceipt.id == m.PurchaseInvoice.goods_receipt_id
    ).outerjoin(
        m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseInvoice.purchase_order_id
    )
    wh_expr = func.coalesce(
        m.PurchaseInvoice.warehouse_id,
        m.GoodsReceipt.warehouse_id,
        m.PurchaseOrder.warehouse_id,
    )
    return stmt.where(wh_expr.in_(managed_wh_ids))


async def resolve_purchase_invoice_warehouse_id(
    db: AsyncSession, inv: m.PurchaseInvoice
) -> str | None:
    """Prefer direct PI.warehouse_id, then GRN, then PO."""
    direct = getattr(inv, "warehouse_id", None)
    if direct:
        return str(direct)
    if getattr(inv, "goods_receipt_id", None):
        grn = await db.get(m.GoodsReceipt, inv.goods_receipt_id)
        if grn and getattr(grn, "warehouse_id", None):
            return str(grn.warehouse_id)
    if getattr(inv, "purchase_order_id", None):
        po = await db.get(m.PurchaseOrder, inv.purchase_order_id)
        if po and getattr(po, "warehouse_id", None):
            return str(po.warehouse_id)
    return None


async def assert_purchase_invoice_in_manager_scope(
    db: AsyncSession, claims: dict, inv: m.PurchaseInvoice
) -> None:
    managed_wh = await managed_warehouse_ids(db, claims)
    if managed_wh is None:
        return
    wid = await resolve_purchase_invoice_warehouse_id(db, inv)
    assert_warehouse_in_manager_scope(managed_wh, wid, allow_unset=False)


async def assert_purchase_invoice_links_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    *,
    goods_receipt_id: str | None,
    purchase_order_id: str | None,
    warehouse_id: str | None = None,
) -> None:
    """Create-time gate: managers need a managed warehouse (explicit or via GRN/PO)."""
    managed_wh = await managed_warehouse_ids(db, claims)
    if managed_wh is None:
        return
    wid = (warehouse_id or "").strip() or None
    if not wid and goods_receipt_id:
        grn = await db.get(m.GoodsReceipt, goods_receipt_id)
        if grn and getattr(grn, "warehouse_id", None):
            wid = str(grn.warehouse_id)
    if not wid and purchase_order_id:
        po = await db.get(m.PurchaseOrder, purchase_order_id)
        if po and getattr(po, "warehouse_id", None):
            wid = str(po.warehouse_id)
    assert_warehouse_in_manager_scope(managed_wh, wid, allow_unset=False)


async def scoped_financial_kpis(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_ids: list[str],
    day_start: datetime,
    yesterday_start: datetime,
    month_start: datetime,
    prior_month_start: datetime,
) -> dict:
    """Sales / expense KPIs limited to managed stores. Purchase invoices use PO/GRN WH join elsewhere."""

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    if not store_ids:
        return {
            "total_sales": 0.0,
            "total_purchases": 0.0,
            "total_expenses": 0.0,
            "daily_revenue": 0.0,
            "yesterday_revenue": 0.0,
            "monthly_revenue": 0.0,
            "prior_month_revenue": 0.0,
            "dod_change_pct": None,
            "mom_change_pct": None,
            "recent_sales": [],
            "top_products": [],
        }

    inv_posted = m.SalesInvoice.status.in_(["posted", "partial", "paid"])
    inv_store = m.SalesInvoice.store_id.in_(store_ids)

    inv_total = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id, inv_posted, inv_store
            )
        )
    )
    inv_daily = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= day_start,
            )
        )
    )
    inv_yesterday = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= yesterday_start,
                m.SalesInvoice.posted_at < day_start,
            )
        )
    )
    inv_monthly = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= month_start,
            )
        )
    )
    inv_prior = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= prior_month_start,
                m.SalesInvoice.posted_at < month_start,
            )
        )
    )

    # POS txs attributed via PosSession.store_id
    async def pos_sum(*extra):
        stmt = (
            select(func.coalesce(func.sum(m.Transaction.total), 0))
            .select_from(m.Transaction)
            .join(m.PosSession, m.Transaction.session_id == m.PosSession.id)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
                m.PosSession.store_id.in_(store_ids),
                *extra,
            )
        )
        return float(await scalar(stmt))

    pos_total = await pos_sum()
    pos_daily = await pos_sum(m.Transaction.created_at >= day_start)
    pos_yesterday = await pos_sum(
        m.Transaction.created_at >= yesterday_start,
        m.Transaction.created_at < day_start,
    )
    pos_monthly = await pos_sum(m.Transaction.created_at >= month_start)
    pos_prior = await pos_sum(
        m.Transaction.created_at >= prior_month_start,
        m.Transaction.created_at < month_start,
    )

    expenses = float(
        await scalar(
            select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.status == "approved",
                m.Expense.store_id.in_(store_ids),
            )
        )
    )

    daily_revenue = pos_daily + inv_daily
    yesterday_revenue = pos_yesterday + inv_yesterday
    monthly_revenue = pos_monthly + inv_monthly
    prior_month_revenue = pos_prior + inv_prior
    dod_change_pct = None
    if yesterday_revenue > 0:
        dod_change_pct = round(((daily_revenue - yesterday_revenue) / yesterday_revenue) * 100, 2)
    mom_change_pct = None
    if prior_month_revenue > 0:
        mom_change_pct = round(
            ((monthly_revenue - prior_month_revenue) / prior_month_revenue) * 100, 2
        )

    recent_invoices = (
        await db.execute(
            select(m.SalesInvoice)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
            )
            .order_by(m.SalesInvoice.posted_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent = [
        {
            "source": "invoice",
            "reference": inv.invoice_number,
            "total": float(inv.total_amount or 0),
            "at": inv.posted_at or inv.created_at,
            "store_id": inv.store_id,
        }
        for inv in recent_invoices
    ]

    top_rows = (
        await db.execute(
            select(
                m.Product.id,
                m.Product.name,
                m.Product.sku,
                func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0).label("qty"),
                func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).label("revenue"),
            )
            .join(m.SalesInvoiceItem, m.SalesInvoiceItem.product_id == m.Product.id)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.Product.tenant_id == tenant_id,
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
            )
            .group_by(m.Product.id, m.Product.name, m.Product.sku)
            .order_by(func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "quantity": float(row.qty or 0),
            "revenue": float(row.revenue or 0),
        }
        for row in top_rows
    ]

    return {
        "total_sales": pos_total + inv_total,
        "total_purchases": 0.0,  # PurchaseInvoice has no store_id — do not leak tenant-wide
        "total_expenses": expenses,
        "daily_revenue": daily_revenue,
        "yesterday_revenue": yesterday_revenue,
        "monthly_revenue": monthly_revenue,
        "prior_month_revenue": prior_month_revenue,
        "dod_change_pct": dod_change_pct,
        "mom_change_pct": mom_change_pct,
        "recent_sales": recent,
        "top_products": top_products,
    }


def apply_bank_statement_store_scope(
    stmt,
    managed_store_ids: list[str] | None,
    *,
    tenant_id: str | None = None,
):
    """Filter bank statements to those a store_manager may list/read/reconcile.

    Fail-closed: hide when any matched line points to a null-store or foreign-store
    journal. Visible when at least one in-scope matched line exists, or the statement
    account still has unmatched book lines in managed stores.
    """
    if managed_store_ids is None:
        return stmt
    if not managed_store_ids:
        return stmt.where(func.false())

    BS = m.BankStatement
    BSL = m.BankStatementLine
    JEL = m.JournalEntryLine
    JE = m.JournalEntry

    foreign_taint = (
        select(BSL.id)
        .select_from(BSL)
        .join(JEL, JEL.id == BSL.matched_journal_line_id)
        .join(JE, JE.id == JEL.journal_entry_id)
        .where(
            BSL.statement_id == BS.id,
            BSL.matched_journal_line_id.is_not(None),
            or_(JE.store_id.is_(None), ~JE.store_id.in_(managed_store_ids)),
        )
    )
    in_scope_match = (
        select(BSL.id)
        .select_from(BSL)
        .join(JEL, JEL.id == BSL.matched_journal_line_id)
        .join(JE, JE.id == JEL.journal_entry_id)
        .where(
            BSL.statement_id == BS.id,
            BSL.matched_journal_line_id.is_not(None),
            JE.store_id.in_(managed_store_ids),
        )
    )
    matched_jl = select(BSL.matched_journal_line_id).where(
        BSL.matched_journal_line_id.is_not(None)
    )
    cleared_jl = select(m.BankClearingBookLink.journal_line_id)
    if tenant_id:
        foreign_taint = foreign_taint.where(BSL.tenant_id == tenant_id)
        in_scope_match = in_scope_match.where(BSL.tenant_id == tenant_id)
        matched_jl = matched_jl.where(BSL.tenant_id == tenant_id)
        cleared_jl = cleared_jl.where(m.BankClearingBookLink.tenant_id == tenant_id)

    in_scope_book = (
        select(JEL.id)
        .select_from(JEL)
        .join(JE, JE.id == JEL.journal_entry_id)
        .where(
            JEL.account_id == BS.account_id,
            JE.store_id.in_(managed_store_ids),
            ~JEL.id.in_(matched_jl),
            ~JEL.id.in_(cleared_jl),
            or_(JEL.debit > 0, JEL.credit > 0),
        )
    )
    if tenant_id:
        in_scope_book = in_scope_book.where(JEL.tenant_id == tenant_id)

    return stmt.where(
        ~exists(foreign_taint.correlate(BS)),
        or_(
            exists(in_scope_match.correlate(BS)),
            exists(in_scope_book.correlate(BS)),
        ),
    )


async def assert_bank_statement_in_manager_scope(
    db: AsyncSession,
    *,
    tenant_id: str,
    statement_id: str,
    managed_store_ids: list[str] | None,
    company_id: str | None = None,
) -> m.BankStatement:
    """403 when a store_manager accesses a bank statement outside managed-store scope."""
    stmt = select(m.BankStatement).where(
        m.BankStatement.id == statement_id,
        m.BankStatement.tenant_id == tenant_id,
    )
    if company_id:
        stmt = stmt.where(m.BankStatement.company_id == company_id)
    stmt = apply_bank_statement_store_scope(
        stmt, managed_store_ids, tenant_id=tenant_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Bank statement is outside your managed store scope.",
                "statement_id": statement_id,
            },
        )
    return row
