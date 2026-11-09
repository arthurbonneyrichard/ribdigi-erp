"""Encrypted tenant logical backup and guarded restore."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException

from app.honesty import money_json, optional_honest_narrative
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

FORMAT_NAME = "ribdigi-logical-backup"
FORMAT_VERSION = 1

# Restore order respects FK dependencies (parents before children).
DATASET_SPECS: list[tuple[str, type]] = [
    ("custom_roles", m.CustomRole),
    ("stores", m.Store),
    ("warehouses", m.Warehouse),
    ("product_categories", m.ProductCategory),
    ("brands", m.Brand),
    ("units_of_measure", m.UnitOfMeasure),
    ("products", m.Product),
    ("product_variants", m.ProductVariant),
    ("product_batches", m.ProductBatch),
    ("batch_holds", m.BatchHold),
    ("warehouse_stocks", m.WarehouseStock),
    ("parties", m.Party),
    ("tax_rates", m.TaxRate),
    ("exchange_rates", m.ExchangeRate),
    ("accounts", m.Account),
    ("expense_categories", m.ExpenseCategory),
    ("purchase_requests", m.PurchaseRequest),
    ("purchase_request_items", m.PurchaseRequestItem),
    ("purchase_orders", m.PurchaseOrder),
    ("purchase_order_items", m.PurchaseOrderItem),
    ("purchase_order_amendments", m.PurchaseOrderAmendment),
    ("goods_receipts", m.GoodsReceipt),
    ("goods_receipt_items", m.GoodsReceiptItem),
    ("purchase_returns", m.PurchaseReturn),
    ("purchase_return_items", m.PurchaseReturnItem),
    ("purchase_invoices", m.PurchaseInvoice),
    ("purchase_invoice_items", m.PurchaseInvoiceItem),
    ("sales_invoices", m.SalesInvoice),
    ("sales_invoice_items", m.SalesInvoiceItem),
    ("prescriptions", m.Prescription),
    ("prescription_items", m.PrescriptionItem),
    ("prescription_attachments", m.PrescriptionAttachment),
    ("customer_payments", m.CustomerPayment),
    ("supplier_payments", m.SupplierPayment),
    ("cheques", m.Cheque),
    ("expenses", m.Expense),
    ("expense_approval_actions", m.ExpenseApprovalAction),
    ("recurring_expenses", m.RecurringExpense),
    ("pos_sessions", m.PosSession),
    ("transactions", m.Transaction),
    ("pos_payments", m.PosPayment),
    ("journal_entries", m.JournalEntry),
    ("journal_entry_lines", m.JournalEntryLine),
    ("bank_statements", m.BankStatement),
    ("bank_account_connections", m.BankAccountConnection),
    ("bank_clearing_groups", m.BankClearingGroup),
    ("bank_statement_lines", m.BankStatementLine),
    ("bank_clearing_book_links", m.BankClearingBookLink),
    ("stock_movements", m.StockMovement),
    ("stock_transfers", m.StockTransfer),
    ("stock_transfer_items", m.StockTransferItem),
    ("stock_counts", m.StockCount),
    ("stock_count_items", m.StockCountItem),
    ("product_images", m.ProductImage),
    ("party_contacts", m.PartyContact),
    ("notification_preferences", m.NotificationPreference),
    ("report_schedules", m.ReportSchedule),
    ("sales_coupons", m.SalesCoupon),
    ("sales_coupon_redemptions", m.SalesCouponRedemption),
    ("other_incomes", m.OtherIncome),
    ("hotel_rooms", m.HotelRoom),
    ("hotel_guests", m.HotelGuest),
    ("hotel_settings", m.HotelSettings),
    ("hotel_reservation_groups", m.HotelReservationGroup),
    ("hotel_reservations", m.HotelReservation),
    ("hotel_folios", m.HotelFolio),
    ("hotel_folio_charges", m.HotelFolioCharge),
    ("hotel_folio_payments", m.HotelFolioPayment),
    ("hotel_housekeeping_tasks", m.HotelHousekeepingTask),
    ("hotel_maintenance_tickets", m.HotelMaintenanceTicket),
    ("hotel_services", m.HotelService),
    ("hotel_rate_plans", m.HotelRatePlan),
    ("hotel_guest_requests", m.HotelGuestRequest),
    ("hotel_lost_found", m.HotelLostFound),
    ("hotel_cashier_shifts", m.HotelCashierShift),
    ("hotel_night_audits", m.HotelNightAudit),
    ("hotel_events", m.HotelEvent),
    ("hotel_booking_links", m.HotelBookingLink),
    ("hotel_shop_sales", m.HotelShopSale),
    ("hotel_shop_sale_lines", m.HotelShopSaleLine),
    ("restaurant_tables", m.RestaurantTable),
    ("restaurant_till_shifts", m.RestaurantTillShift),
    ("restaurant_till_cash_moves", m.RestaurantTillCashMove),
    ("restaurant_menu_settings", m.RestaurantMenuSettings),
    ("restaurant_menu_categories", m.RestaurantMenuCategory),
    ("restaurant_menu_items", m.RestaurantMenuItem),
    ("restaurant_modifier_groups", m.RestaurantModifierGroup),
    ("restaurant_modifiers", m.RestaurantModifier),
    ("restaurant_recipes", m.RestaurantRecipe),
    ("restaurant_recipe_lines", m.RestaurantRecipeLine),
    ("restaurant_orders", m.RestaurantOrder),
    ("restaurant_order_lines", m.RestaurantOrderLine),
    ("restaurant_order_modifiers", m.RestaurantOrderModifier),
    ("restaurant_kitchen_tickets", m.RestaurantKitchenTicket),
    ("restaurant_bookings", m.RestaurantBooking),
    ("restaurant_booking_links", m.RestaurantBookingLink),
    ("branches", m.Branch),
    ("departments", m.Department),
    ("customer_groups", m.CustomerGroup),
    ("product_price_tiers", m.ProductPriceTier),
    ("user_store_memberships", m.UserStoreMembership),
    ("sales_quotations", m.SalesQuotation),
    ("sales_quotation_items", m.SalesQuotationItem),
    ("sales_orders", m.SalesOrder),
    ("sales_order_items", m.SalesOrderItem),
    ("stock_reservations", m.StockReservation),
    ("sales_returns", m.SalesReturn),
    ("sales_return_items", m.SalesReturnItem),
    ("purchase_request_approval_actions", m.PurchaseRequestApprovalAction),
    ("cash_transfers", m.CashTransfer),
    ("gift_cards", m.GiftCard),
    ("pos_cash_movements", m.PosCashMovement),
    ("ai_report_templates", m.AiReportTemplate),
    ("fmcg_routes", m.FmcgRoute),
    ("fmcg_route_stops", m.FmcgRouteStop),
    ("fmcg_customer_assignments", m.FmcgCustomerAssignment),
    ("fmcg_dispatches", m.FmcgDispatch),
    ("fmcg_trade_schemes", m.FmcgTradeScheme),
    ("fmcg_orders", m.FmcgOrder),
    ("fmcg_order_lines", m.FmcgOrderLine),
    ("fmcg_payments", m.FmcgPayment),
    ("fmcg_returns", m.FmcgReturn),
    ("fmcg_return_lines", m.FmcgReturnLine),
    ("hospital_patients", m.HospitalPatient),
    ("hospital_encounters", m.HospitalEncounter),
    ("ecommerce_storefronts", m.EcommerceStorefront),
    ("ecommerce_domains", m.EcommerceDomain),
    ("ecommerce_gateways", m.EcommerceGateway),
    ("ecommerce_connectors", m.EcommerceConnector),
    ("ecommerce_listings", m.EcommerceListing),
    ("ecommerce_shoppers", m.EcommerceShopper),
    ("ecommerce_orders", m.EcommerceOrder),
    ("ecommerce_order_items", m.EcommerceOrderItem),
    ("ecommerce_payment_events", m.EcommercePaymentEvent),
    ("ecommerce_reservations", m.EcommerceReservation),
    ("checkout_payment_notices", m.CheckoutPaymentNotice),
    ("bakery_recipes", m.BakeryRecipe),
    ("bakery_recipe_lines", m.BakeryRecipeLine),
    ("bakery_batches", m.BakeryBatch),
    ("bakery_waste", m.BakeryWaste),
    ("bakery_till_shifts", m.BakeryTillShift),
    ("bakery_orders", m.BakeryOrder),
    ("bakery_order_lines", m.BakeryOrderLine),
    ("bakery_sales", m.BakerySale),
    ("bakery_sale_lines", m.BakerySaleLine),
    ("bakery_payments", m.BakeryPayment),
    ("bakery_stock_receipts", m.BakeryStockReceipt),
    ("bakery_expenses", m.BakeryExpense),
    ("gym_plans", m.GymPlan),
    ("gym_members", m.GymMember),
    ("gym_memberships", m.GymMembership),
    ("gym_till_shifts", m.GymTillShift),
    ("gym_payments", m.GymPayment),
    ("gym_check_ins", m.GymCheckIn),
    ("gym_classes", m.GymClass),
    ("gym_class_bookings", m.GymClassBooking),
    ("hrm_settings", m.HrmSettings),
    ("hrm_employees", m.HrmEmployee),
    ("hrm_leave_requests", m.HrmLeaveRequest),
    ("hrm_attendance", m.HrmAttendance),
    ("hrm_payroll_runs", m.HrmPayrollRun),
    ("hrm_payslips", m.HrmPayslip),
]

# Every company table is either backed up above or listed here with the reason it is not.
# tests/test_backup_coverage.py fails on a table that is in neither, so none can be forgotten.
_SIGN_IN = "Sign-in or secret material. Restoring it would revive old access."
_PASSING = "Short-lived working data with no lasting business record."
_PAIRING = "Device pairing. Hardware pairs again after a restore."
_PLATFORM = "Belongs to RIBDIGI's own records, not the company's data."
BACKUP_EXCLUDED: dict[str, str] = {
    "users": "Restore runs as a signed-in user, and passwords are never in a backup. An old copy must not undo role or access changes.",
    "auth_sessions": _SIGN_IN,
    "auth_tokens": _SIGN_IN,
    "two_factor_backup_codes": _SIGN_IN,
    "webauthn_credentials": _SIGN_IN,
    "webauthn_challenges": _SIGN_IN,
    "api_keys": _SIGN_IN,
    "pos_cashier_passcodes": _SIGN_IN,
    "pos_operator_sessions": _SIGN_IN,
    "pos_unlock_throttles": _SIGN_IN,
    "webhook_endpoints": "The signing secret is never in a backup, so an endpoint is set up again with a new one.",
    "webhook_deliveries": _PASSING,
    "audit_logs": "Tamper-evident chain. A restore must not rewrite history, and the log has its own archive.",
    "audit_cold_archives": "Index of the audit log's own archive.",
    "backup_jobs": "History of backups, kept outside the data they restore.",
    "backup_settings": "A restore must not change the schedule protecting the company now.",
    "notifications": _PASSING,
    "ai_queries": _PASSING,
    "ai_security_alerts": _PASSING,
    "ecommerce_carts": _PASSING,
    "ecommerce_cart_items": _PASSING,
    "ecommerce_sync_jobs": _PASSING,
    "offline_grants": _PASSING,
    "offline_stock_allocations": _PASSING,
    "offline_sync_events": _PASSING,
    "print_jobs": _PASSING,
    "print_job_attempts": _PASSING,
    "print_agents": _PAIRING,
    "printers": _PAIRING,
    "pos_devices": _PAIRING,
    "support_tickets": _PLATFORM,
    "support_ticket_messages": _PLATFORM,
    "support_ticket_events": _PLATFORM,
    "support_ticket_attachments": _PLATFORM,
    "support_email_outbox": _PLATFORM,
    "tenant_billing_accounts": _PLATFORM,
    "tenant_billing_invoices": _PLATFORM,
    "tenant_billing_attempts": _PLATFORM,
    "tenant_billing_events": _PLATFORM,
}


# Each desk is its own product: a company's backup only ever reads its own desk's tables.
_DESK_TABLES = {
    "hotel_": "hotel",
    "restaurant_": "restaurant",
    "hospital_": "hospital",
    "fmcg_": "fmcg",
    "bakery_": "bakery",
    "gym_": "gym",
    "hrm_": "hrm",
}


def _desk_of(table: str) -> str | None:
    return next((desk for prefix, desk in _DESK_TABLES.items() if table.startswith(prefix)), None)


def _parents_first(specs: list[tuple[str, type]]) -> list[tuple[str, type]]:
    """Order datasets so a row is restored after the rows it points at.

    Keeps the listed order where it can. A true cycle is broken at the first table listed,
    and the links it leaves pointing forward are filled in afterwards (see _late_columns).
    """
    by_table = {model.__table__.name: (name, model) for name, model in specs}
    needs = {
        table: {
            fk.column.table.name
            for fk in model.__table__.foreign_keys
            if fk.column.table.name in by_table and fk.column.table.name != table
        }
        for table, (_name, model) in by_table.items()
    }
    placed: list[str] = []
    waiting = [model.__table__.name for _name, model in specs]
    while waiting:
        ready = next((t for t in waiting if needs[t] <= set(placed)), waiting[0])
        placed.append(ready)
        waiting.remove(ready)
    return [by_table[table] for table in placed]


DATASET_SPECS = _parents_first(DATASET_SPECS)


def _late_columns(model: type) -> list[str]:
    """Links to a row that may not exist yet when this table restores: to itself, or to a later table."""
    position = {spec.__table__.name: index for index, (_name, spec) in enumerate(DATASET_SPECS)}
    own = position[model.__table__.name]
    return [
        fk.parent.name
        for fk in model.__table__.foreign_keys
        if position.get(fk.column.table.name, -1) >= own
    ]


def backup_root() -> Path:
    root = Path(settings.BACKUP_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _confined_tenant_backup_file(job: m.BackupJob) -> Path | None:
    raw = (job.storage_path or "").strip()
    if not raw or not job.tenant_id:
        return None
    root = (backup_root() / job.tenant_id).resolve()
    try:
        resolved = Path(raw).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def _fernet_from_configured_key(raw: str, *, label: str) -> Fernet:
    """Accept a Fernet key, or common openssl formats (hex / standard base64)."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("empty key")

    try:
        return Fernet(value.encode("utf-8") if isinstance(value, str) else value)
    except Exception:
        pass

    if len(value) == 64:
        try:
            return Fernet(base64.urlsafe_b64encode(bytes.fromhex(value)))
        except Exception:
            pass

    try:
        decoded = base64.b64decode(value, validate=False)
        if len(decoded) == 32:
            return Fernet(base64.urlsafe_b64encode(decoded))
    except Exception:
        pass

    raise HTTPException(
        status_code=500,
        detail=(
            f"Invalid {label}: use a Fernet key from "
            '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
            "or a 64-character hex value from `openssl rand -hex 32`. "
            "Do not leave REPLACE_ME placeholders."
        ),
    )


def _fernet() -> Fernet:
    raw = (settings.BACKUP_ENCRYPTION_KEY or "").strip()
    if raw:
        return _fernet_from_configured_key(raw, label="BACKUP_ENCRYPTION_KEY")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ribdigi-backup-v1",
        iterations=120_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.JWT_SECRET_KEY.encode("utf-8")))
    return Fernet(key)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return money_json(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def _is_secret_column(name: str) -> bool:
    key = name.lower()
    return (
        "password" in key
        or "secret" in key
        or key in {"token_hash", "api_key_hash", "refresh_token", "session_token"}
    )


def row_to_dict(obj: Any) -> dict:
    data: dict[str, Any] = {}
    for col in obj.__table__.columns:
        if _is_secret_column(col.name):
            continue
        data[col.name] = getattr(obj, col.name)
    return json.loads(json.dumps(data, default=_json_default))


def serialize_job(job: m.BackupJob) -> dict:
    return {
        "id": job.id,
        "tenant_id": job.tenant_id,
        "status": job.status,
        "filename": job.filename,
        "size_bytes": job.size_bytes,
        "checksum_sha256": job.checksum_sha256,
        "encrypted": job.encrypted,
        "record_counts": job.record_counts or {},
        "created_by": job.created_by,
        "created_at": job.created_at,
        "error_message": job.error_message,
        "notes": job.notes,
        # storage_path / destination credentials never serialized
    }


def serialize_settings(row: m.BackupSettings) -> dict:
    return {
        "enabled": row.enabled,
        "frequency": row.frequency,
        "retention_count": row.retention_count,
        "hour_utc": row.hour_utc,
        "last_run_at": row.last_run_at,
        "updated_at": row.updated_at,
    }


async def get_or_create_settings(db: AsyncSession, tenant_id: str) -> m.BackupSettings:
    row = (
        await db.execute(select(m.BackupSettings).where(m.BackupSettings.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row:
        return row
    row = m.BackupSettings(
        tenant_id=tenant_id,
        enabled=False,
        frequency="daily",
        retention_count=settings.BACKUP_RETENTION_COUNT,
        hour_utc=2,
    )
    db.add(row)
    await db.flush()
    return row


async def update_settings(
    db: AsyncSession,
    tenant_id: str,
    *,
    enabled: bool | None = None,
    frequency: str | None = None,
    retention_count: int | None = None,
    hour_utc: int | None = None,
) -> m.BackupSettings:
    row = await get_or_create_settings(db, tenant_id)
    if enabled is not None:
        row.enabled = enabled
    if frequency is not None:
        # Defense in depth: BackupSettingsUpdate.frequency Literal rejects
        # blank/unknown with 422 before this runs.
        if frequency not in {"daily", "weekly"}:
            raise HTTPException(status_code=400, detail="frequency must be daily or weekly")
        row.frequency = frequency
    if retention_count is not None:
        if retention_count < 1 or retention_count > 365:
            raise HTTPException(status_code=400, detail="retention_count must be 1–365")
        row.retention_count = retention_count
    if hour_utc is not None:
        if hour_utc < 0 or hour_utc > 23:
            raise HTTPException(status_code=400, detail="hour_utc must be 0–23")
        row.hour_utc = hour_utc
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def collect_tenant_payload(db: AsyncSession, tenant_id: str) -> tuple[dict, dict[str, int]]:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from app import packages as packages_svc

    stored = getattr(tenant, "industry", None)
    industry = packages_svc.canonicalize_industry(stored) or str(stored or "").strip().lower()
    datasets: dict[str, list] = {}
    counts: dict[str, int] = {}
    for name, model in DATASET_SPECS:
        desk = _desk_of(model.__table__.name)
        if desk is not None and desk != industry:
            datasets[name] = []
            counts[name] = 0
            continue
        rows = (
            await db.execute(select(model).where(model.tenant_id == tenant_id))
        ).scalars().all()
        datasets[name] = [row_to_dict(r) for r in rows]
        counts[name] = len(datasets[name])

    from app.storage import read_object

    files: dict[str, str] = {}
    missing: list[str] = []
    for rows in datasets.values():
        for row in rows:
            key = row.get("storage_key")
            if not key or key in files or key in missing:
                continue
            try:
                obj = read_object(str(key), tenant_id=tenant_id)
            except HTTPException:
                missing.append(str(key))
                continue
            files[str(key)] = base64.b64encode(obj.data).decode("ascii")
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"Backup incomplete. Missing stored files: {', '.join(missing[:5])}",
        )
    counts["files"] = len(files)

    payload = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "tenant_id": tenant_id,
        "tenant": {
            "id": tenant.id,
            "slug": tenant.slug,
            "company_name": tenant.company_name,
            "industry": tenant.industry,
            "currency": tenant.currency,
            "status": tenant.status,
            "expense_approval_threshold": money_json(
                tenant.expense_approval_threshold or 0
            ),
            "expense_l2_threshold": money_json(
                getattr(tenant, "expense_l2_threshold", None), default=1000.0
            ),
            "expense_approval_matrix": getattr(tenant, "expense_approval_matrix", None),
            "tax_jurisdiction": getattr(tenant, "tax_jurisdiction", None) or "GH",
            "tax_registration_number": getattr(tenant, "tax_registration_number", None),
            "tax_filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
            "early_pay_discount_pct": money_json(
                getattr(tenant, "early_pay_discount_pct", None) or 0
            ),
            "early_pay_discount_days": int(getattr(tenant, "early_pay_discount_days", None) or 0),
        },
        "created_at": datetime.utcnow().isoformat(),
        "datasets": datasets,
        "files": files,
    }
    return payload, counts


def encrypt_payload(payload: dict) -> tuple[bytes, str, str]:
    """Return (file_bytes, checksum_of_file, checksum_of_plain)."""
    plain = gzip.compress(
        json.dumps(payload, sort_keys=True, default=_json_default).encode("utf-8"),
        compresslevel=6,
        mtime=0,
    )
    plain_checksum = hashlib.sha256(plain).hexdigest()
    token = _fernet().encrypt(plain)
    envelope = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "encrypted": True,
        "plain_sha256": plain_checksum,
        "ciphertext_b64": base64.b64encode(token).decode("ascii"),
    }
    file_bytes = json.dumps(envelope, sort_keys=True).encode("utf-8")
    file_checksum = hashlib.sha256(file_bytes).hexdigest()
    return file_bytes, file_checksum, plain_checksum


def decrypt_archive(file_bytes: bytes, expected_file_checksum: str | None = None) -> dict:
    if expected_file_checksum:
        actual = hashlib.sha256(file_bytes).hexdigest()
        if actual != expected_file_checksum:
            raise HTTPException(status_code=400, detail="Backup file checksum mismatch")
    try:
        envelope = json.loads(file_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid backup archive: {exc}") from exc
    if envelope.get("format") != FORMAT_NAME:
        raise HTTPException(status_code=400, detail="Unsupported backup format")
    try:
        token = base64.b64decode(envelope["ciphertext_b64"])
        plain = _fernet().decrypt(token)
    except (InvalidToken, KeyError, Exception) as exc:
        raise HTTPException(status_code=400, detail="Unable to decrypt backup (wrong key or corrupt file)") from exc
    plain_checksum = hashlib.sha256(plain).hexdigest()
    if envelope.get("plain_sha256") and envelope["plain_sha256"] != plain_checksum:
        raise HTTPException(status_code=400, detail="Decrypted payload checksum mismatch")
    try:
        payload = json.loads(gzip.decompress(plain).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Corrupt backup payload: {exc}") from exc
    if payload.get("format") != FORMAT_NAME:
        raise HTTPException(status_code=400, detail="Unsupported inner backup format")
    return payload


async def create_backup(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    notes: str | None = None,
) -> m.BackupJob:
    job = m.BackupJob(
        tenant_id=tenant_id,
        status="pending",
        filename="",
        storage_path="",
        size_bytes=0,
        checksum_sha256="",
        encrypted=True,
        record_counts={},
        created_by=user_id,
        notes=optional_honest_narrative(notes, label="backup notes"),
    )
    db.add(job)
    await db.flush()

    try:
        payload, counts = await collect_tenant_payload(db, tenant_id)
        file_bytes, file_checksum, _plain = encrypt_payload(payload)
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"{stamp}_{job.id[:8]}.ribbak"
        tenant_dir = backup_root() / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        path = tenant_dir / filename
        path.write_bytes(file_bytes)

        job.status = "completed"
        job.filename = filename
        job.storage_path = str(path)
        job.size_bytes = len(file_bytes)
        job.checksum_sha256 = file_checksum
        job.record_counts = counts
        await db.flush()

        settings_row = await get_or_create_settings(db, tenant_id)
        settings_row.last_run_at = datetime.utcnow()
        await prune_retention(db, tenant_id, settings_row.retention_count)
        await db.flush()
        return job
    except HTTPException as exc:
        job.status = "failed"
        job.error_message = str(exc.detail)[:500] if exc.detail else "Backup failed"
        await db.flush()
        # Manual creates still raise; scheduled path catches and notifies.
        if notes != "scheduled":
            await notify_backup_failure(
                db,
                tenant_id=tenant_id,
                reason="failed",
                detail=str(exc.detail),
            )
        raise
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:500]
        await db.flush()
        if notes != "scheduled":
            await notify_backup_failure(
                db,
                tenant_id=tenant_id,
                reason="failed",
                detail=str(exc)[:400],
            )
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc


async def list_backups(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[m.BackupJob]:
    stmt = (
        select(m.BackupJob)
        .where(m.BackupJob.tenant_id == tenant_id)
        .order_by(m.BackupJob.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if status is not None:
        # Schema BackupJobStatusFilterValue rejects blank/invalid → 422;
        # keep allow-list defense-in-depth (no silent empty filter / blank→all).
        wanted = (status or "").strip().lower()
        allowed = {"pending", "completed", "failed", "restoring"}
        if not wanted:
            pass
        elif wanted not in allowed:
            raise HTTPException(
                status_code=422,
                detail="status must be pending, completed, failed, or restoring",
            )
        else:
            stmt = stmt.where(m.BackupJob.status == wanted)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_backup(db: AsyncSession, tenant_id: str, backup_id: str) -> m.BackupJob:
    job = await db.get(m.BackupJob, backup_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Backup not found")
    return job


async def read_backup_bytes(job: m.BackupJob) -> bytes:
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Backup is not available for download")
    path = _confined_tenant_backup_file(job)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file missing on disk")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if job.checksum_sha256 and actual != job.checksum_sha256:
        raise HTTPException(status_code=409, detail="Stored backup failed integrity check")
    return data


def _parse_value(model: type, key: str, value: Any) -> Any:
    if value is None:
        return None
    col = model.__table__.columns.get(key)
    if col is None:
        return value
    python_type = col.type.python_type if hasattr(col.type, "python_type") else None
    if python_type is datetime and isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return value
    if python_type is date and isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value


async def validate_restore_payload(payload: dict, tenant_id: str) -> dict:
    if payload.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Backup tenant_id does not match current tenant (cross-tenant restore blocked)",
        )
    datasets = payload.get("datasets") or {}
    counts = {name: len(datasets.get(name) or []) for name, _ in DATASET_SPECS}
    unknown = sorted(set(datasets.keys()) - {name for name, _ in DATASET_SPECS})
    return {
        "valid": True,
        "format": payload.get("format"),
        "version": payload.get("version"),
        "source_tenant_id": payload.get("tenant_id"),
        "record_counts": counts,
        "unknown_datasets": unknown,
        "company_name": (payload.get("tenant") or {}).get("company_name"),
    }


async def _clear_regenerated_account(
    db: AsyncSession, tenant_id: str, pk: str, code: str | None, *, keep: set[str]
) -> None:
    """Opening Accounting on an empty company recreates the default accounts under new ids.

    The restored account takes their place. If money was posted to one since, it is not ours to
    remove, so the restore stops rather than leave two accounts with the same code.
    """
    rows = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code, m.Account.id != pk)
        )
    ).scalars().all()
    rows = [row for row in rows if row.id not in keep]
    for row in rows:
        used = (
            await db.execute(select(m.JournalEntryLine.id).where(m.JournalEntryLine.account_id == row.id).limit(1))
        ).first()
        if used:
            raise HTTPException(
                status_code=409,
                detail=f"Account {code} has entries posted since this backup. Move them before restoring.",
            )
        await db.delete(row)
    if rows:
        await db.flush()


async def apply_restore(db: AsyncSession, tenant_id: str, payload: dict) -> dict:
    report = await validate_restore_payload(payload, tenant_id)
    datasets = payload.get("datasets") or {}
    restored: dict[str, int] = {}
    links_to_fill: list[tuple[type, str, dict[str, Any]]] = []
    backed_up_accounts = {str(row.get("id")) for row in datasets.get("accounts") or []}

    for name, model in DATASET_SPECS:
        rows = datasets.get(name) or []
        count = 0
        late = _late_columns(model)
        for raw in rows:
            data = {k: _parse_value(model, k, v) for k, v in dict(raw).items() if k in model.__table__.columns}
            data["tenant_id"] = tenant_id
            pk = data.get("id")
            if not pk:
                continue
            links = {k: data.pop(k) for k in late if data.get(k) is not None}
            if links:
                links_to_fill.append((model, pk, links))
            existing = await db.get(model, pk)
            if existing:
                if existing.tenant_id != tenant_id:
                    raise HTTPException(
                        status_code=409,
                        detail=f"ID collision for {name}:{pk} belongs to another tenant",
                    )
                for key, value in data.items():
                    setattr(existing, key, value)
            else:
                if model is m.Account:
                    await _clear_regenerated_account(db, tenant_id, pk, data.get("code"), keep=backed_up_accounts)
                if model is m.EcommerceShopper:
                    # The password is never in a backup. A lost shopper sets a new one with a reset.
                    from app.security import hash_password

                    data.setdefault("password_hash", hash_password(uuid4().hex))
                db.add(model(**data))
            count += 1
        restored[name] = count
        await db.flush()

    for model, pk, links in links_to_fill:
        row = await db.get(model, pk)
        for key, value in links.items():
            setattr(row, key, value)
    await db.flush()

    from app.storage import _put_bytes, content_type_for_key, validate_key

    written = 0
    for key, encoded in (payload.get("files") or {}).items():
        safe = validate_key(str(key), tenant_id=tenant_id)
        _put_bytes(safe, base64.b64decode(encoded), content_type_for_key(safe))
        written += 1
    report["files_restored"] = written
    report["restored"] = restored
    report["applied"] = True
    report["proof"] = await prove_restore_integrity(db, tenant_id, payload)
    if not report["proof"].get("ok"):
        raise HTTPException(
            status_code=409,
            detail="Restore verification failed. Database and files were not left as a successful restore.",
        )
    return report


_PROOF_FIELDS: dict[str, tuple[str, ...]] = {
    "products": ("name", "sku", "stock_qty"),
    "parties": ("name", "kind", "status"),
    "stores": ("name", "code", "is_active"),
    "warehouses": ("name", "code", "is_active"),
    "accounts": ("code", "name", "account_type"),
    "sales_invoices": ("invoice_number", "status", "total_amount"),
    "purchase_orders": ("po_number", "status"),
}


def _proof_values_equal(expected: Any, actual: Any) -> bool:
    if expected is None and actual is None:
        return True
    if isinstance(expected, (int, float, Decimal)) or isinstance(actual, (int, float, Decimal)):
        try:
            return money_json(expected or 0) == money_json(actual or 0)
        except (TypeError, ValueError):
            return str(expected) == str(actual)
    return str(expected) == str(actual)


async def prove_restore_integrity(
    db: AsyncSession,
    tenant_id: str,
    payload: dict,
    *,
    sample_limit: int = 100,
) -> dict:
    """Compare live tenant rows to a decrypted backup payload (restore proof).

    Logical restore is upsert-only: rows created after the backup may remain.
    Proof checks that every sampled backup row is present with matching fields.
    """
    datasets = payload.get("datasets") or {}
    mismatches: list[dict[str, Any]] = []
    checked = 0
    by_dataset: dict[str, dict[str, int]] = {}

    for name, model in DATASET_SPECS:
        rows = datasets.get(name) or []
        dataset_checked = 0
        dataset_bad = 0
        fields = _PROOF_FIELDS.get(name, ("name", "status"))
        for raw in rows[:sample_limit]:
            pk = (raw or {}).get("id")
            if not pk:
                continue
            checked += 1
            dataset_checked += 1
            live = await db.get(model, pk)
            if live is None or getattr(live, "tenant_id", None) != tenant_id:
                dataset_bad += 1
                mismatches.append({"dataset": name, "id": pk, "error": "missing"})
                continue
            for field in fields:
                if field not in raw or not hasattr(live, field):
                    continue
                actual = getattr(live, field)
                if not _proof_values_equal(raw[field], actual):
                    dataset_bad += 1
                    mismatches.append(
                        {
                            "dataset": name,
                            "id": pk,
                            "field": field,
                            "expected": raw[field],
                            "actual": actual
                            if not isinstance(actual, Decimal)
                            else money_json(actual),
                        }
                    )
                    break
        by_dataset[name] = {"checked": dataset_checked, "mismatches": dataset_bad}

    return {
        "ok": len(mismatches) == 0,
        "checked": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
        "by_dataset": by_dataset,
        "sample_limit": sample_limit,
        "mode": "upsert_field_match",
    }


async def verify_backup(
    db: AsyncSession,
    *,
    tenant_id: str,
    backup_id: str,
    sample_limit: int = 100,
) -> dict:
    """Decrypt backup, validate tenant binding, and prove against live data."""
    job = await get_backup(db, tenant_id, backup_id)
    file_bytes = await read_backup_bytes(job)
    payload = decrypt_archive(file_bytes, expected_file_checksum=job.checksum_sha256)
    report = await validate_restore_payload(payload, tenant_id)
    proof = await prove_restore_integrity(
        db, tenant_id, payload, sample_limit=sample_limit
    )
    report["proof"] = proof
    report["backup_id"] = backup_id
    report["checksum_sha256"] = job.checksum_sha256
    report["filename"] = job.filename
    return report


async def restore_backup(
    db: AsyncSession,
    *,
    tenant_id: str,
    backup_id: str,
    dry_run: bool = True,
    confirm: bool = False,
    user_id: str | None = None,
) -> dict:
    job = await get_backup(db, tenant_id, backup_id)
    file_bytes = await read_backup_bytes(job)
    payload = decrypt_archive(file_bytes, expected_file_checksum=job.checksum_sha256)
    if dry_run or not confirm:
        report = await validate_restore_payload(payload, tenant_id)
        report["dry_run"] = True
        report["applied"] = False
        return report
    job.status = "restoring"
    await db.flush()
    from app.audit import record_event

    safety = await create_backup(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        notes="safety before restore",
    )
    await record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="backup",
        action="restore_started",
        entity="backup",
        entity_id=backup_id,
        details={"safety_backup_id": safety.id, "filename": job.filename},
    )
    try:
        # A savepoint, so a failed restore undoes itself and leaves the session able to report it.
        async with db.begin_nested():
            report = await apply_restore(db, tenant_id, payload)
        job.status = "completed"
        await db.flush()
        report["dry_run"] = False
        report["safety_backup_id"] = safety.id
        await record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            module="backup",
            action="restore_completed",
            entity="backup",
            entity_id=backup_id,
            details={"safety_backup_id": safety.id, "files_restored": report.get("files_restored", 0)},
        )
        return report
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(getattr(exc, "detail", exc))[:500]
        recovered = False
        try:
            safety_bytes = await read_backup_bytes(safety)
            safety_payload = decrypt_archive(
                safety_bytes, expected_file_checksum=safety.checksum_sha256
            )
            async with db.begin_nested():
                await apply_restore(db, tenant_id, safety_payload)
            recovered = True
        except Exception:
            recovered = False
        await db.flush()
        await record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            module="backup",
            action="restore_failed",
            entity="backup",
            entity_id=backup_id,
            details={"safety_backup_id": safety.id, "safety_restored": recovered},
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Restore failed",
                "safety_backup_id": safety.id,
                "safety_restored": recovered,
            },
        ) from exc


async def prune_retention(db: AsyncSession, tenant_id: str, keep: int) -> int:
    keep = max(1, keep)
    rows = (
        await db.execute(
            select(m.BackupJob)
            .where(m.BackupJob.tenant_id == tenant_id, m.BackupJob.status == "completed")
            .order_by(m.BackupJob.created_at.desc())
        )
    ).scalars().all()
    removed = 0
    for job in rows[keep:]:
        path = _confined_tenant_backup_file(job)
        if path is not None and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        await db.delete(job)
        removed += 1
    return removed


def ensure_backup_dir_writable() -> None:
    try:
        root = backup_root()
        probe = root / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="Backups are temporarily unavailable.",
        ) from exc


async def notify_backup_failure(
    db: AsyncSession,
    *,
    tenant_id: str,
    reason: str,
    detail: str | None = None,
) -> None:
    """Create an in-app system alert for admins when a backup fails (BR-16.2)."""
    from app import notifications as notifications_svc

    reason_s = (reason or "failed").strip()[:80]
    detail_s = (detail or "").strip()[:400]
    message = f"Backup failed ({reason_s})"
    if detail_s:
        message = f"{message}: {detail_s}"
    await notifications_svc.create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Backup failed",
        message=message[:500],
        roles=["company_admin", "super_admin"],
        entity_type="backup",
        entity_id=None,
    )


async def run_scheduled_backup_if_due(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
) -> dict:
    """Run a backup when schedule is enabled and due. Safe for Celery/cron.

    Never raises for expected schedule/create failures — returns ``ran=false`` with a
    reason so the Celery tenant loop can commit the failed job + admin notification.
    """
    from datetime import timedelta

    row = await get_or_create_settings(db, tenant_id)
    if not row.enabled:
        return {"ran": False, "reason": "schedule_disabled", "tenant_id": tenant_id}
    now = datetime.utcnow()
    if row.last_run_at:
        gap = timedelta(days=7 if row.frequency == "weekly" else 1)
        if now - row.last_run_at < gap:
            return {"ran": False, "reason": "already_ran", "tenant_id": tenant_id}
    if now.hour < int(row.hour_utc or 0) and row.last_run_at:
        return {"ran": False, "reason": "before_hour", "tenant_id": tenant_id}

    try:
        ensure_backup_dir_writable()
    except HTTPException as exc:
        await notify_backup_failure(
            db,
            tenant_id=tenant_id,
            reason="dir_not_writable",
            detail=str(exc.detail),
        )
        return {
            "ran": False,
            "reason": "dir_not_writable",
            "tenant_id": tenant_id,
            "error": str(exc.detail)[:200],
        }

    try:
        job = await create_backup(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            notes="scheduled",
        )
        return {
            "ran": True,
            "reason": "created",
            "tenant_id": tenant_id,
            "backup_id": job.id,
            "filename": job.filename,
        }
    except HTTPException as exc:
        await notify_backup_failure(
            db,
            tenant_id=tenant_id,
            reason="failed",
            detail=str(exc.detail),
        )
        return {
            "ran": False,
            "reason": "failed",
            "tenant_id": tenant_id,
            "error": str(exc.detail)[:200],
        }
    except Exception as exc:  # noqa: BLE001 — scheduled path must not crash the tenant loop
        await notify_backup_failure(
            db,
            tenant_id=tenant_id,
            reason="failed",
            detail=str(exc)[:400],
        )
        return {
            "ran": False,
            "reason": "failed",
            "tenant_id": tenant_id,
            "error": str(exc)[:200],
        }
