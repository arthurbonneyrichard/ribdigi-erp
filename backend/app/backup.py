"""Encrypted tenant logical backup and guarded restore."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

FORMAT_NAME = "ribdigi-logical-backup"
FORMAT_VERSION = 1

# Restore order respects FK dependencies (parents before children).
DATASET_SPECS: list[tuple[str, type]] = [
    ("stores", m.Store),
    ("warehouses", m.Warehouse),
    ("product_categories", m.ProductCategory),
    ("brands", m.Brand),
    ("units_of_measure", m.UnitOfMeasure),
    ("products", m.Product),
    ("product_variants", m.ProductVariant),
    ("product_batches", m.ProductBatch),
    ("warehouse_stocks", m.WarehouseStock),
    ("parties", m.Party),
    ("party_contacts", m.PartyContact),
    ("tax_rates", m.TaxRate),
    ("exchange_rates", m.ExchangeRate),
    ("accounts", m.Account),
    ("expense_categories", m.ExpenseCategory),
    ("purchase_requests", m.PurchaseRequest),
    ("purchase_request_items", m.PurchaseRequestItem),
    ("purchase_request_approval_actions", m.PurchaseRequestApprovalAction),
    ("purchase_orders", m.PurchaseOrder),
    ("purchase_order_items", m.PurchaseOrderItem),
    ("goods_receipts", m.GoodsReceipt),
    ("goods_receipt_items", m.GoodsReceiptItem),
    ("purchase_returns", m.PurchaseReturn),
    ("purchase_return_items", m.PurchaseReturnItem),
    ("purchase_invoices", m.PurchaseInvoice),
    ("purchase_invoice_items", m.PurchaseInvoiceItem),
    ("sales_invoices", m.SalesInvoice),
    ("sales_invoice_items", m.SalesInvoiceItem),
    ("customer_payments", m.CustomerPayment),
    ("supplier_payments", m.SupplierPayment),
    ("cheques", m.Cheque),
    ("expenses", m.Expense),
    ("expense_approval_actions", m.ExpenseApprovalAction),
    ("recurring_expenses", m.RecurringExpense),
    ("pos_sessions", m.PosSession),
    ("transactions", m.Transaction),
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
    ("notification_preferences", m.NotificationPreference),
    ("report_schedules", m.ReportSchedule),
]


def backup_root() -> Path:
    root = Path(settings.BACKUP_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fernet() -> Fernet:
    raw = (settings.BACKUP_ENCRYPTION_KEY or "").strip()
    if raw:
        try:
            return Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Invalid BACKUP_ENCRYPTION_KEY: {exc}") from exc
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
        return float(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def row_to_dict(obj: Any) -> dict:
    data: dict[str, Any] = {}
    for col in obj.__table__.columns:
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

    datasets: dict[str, list] = {}
    counts: dict[str, int] = {}
    for name, model in DATASET_SPECS:
        rows = (
            await db.execute(select(model).where(model.tenant_id == tenant_id))
        ).scalars().all()
        datasets[name] = [row_to_dict(r) for r in rows]
        counts[name] = len(datasets[name])

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
            "expense_approval_threshold": float(tenant.expense_approval_threshold or 0),
            "expense_l2_threshold": float(getattr(tenant, "expense_l2_threshold", None) or 1000),
            "expense_approval_matrix": getattr(tenant, "expense_approval_matrix", None),
            "purchase_request_approval_matrix": getattr(
                tenant, "purchase_request_approval_matrix", None
            ),
            "tax_jurisdiction": getattr(tenant, "tax_jurisdiction", None) or "GH",
            "tax_registration_number": getattr(tenant, "tax_registration_number", None),
            "tax_filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
            "early_pay_discount_pct": float(getattr(tenant, "early_pay_discount_pct", None) or 0),
            "early_pay_discount_days": int(getattr(tenant, "early_pay_discount_days", None) or 0),
        },
        "created_at": datetime.utcnow().isoformat(),
        "datasets": datasets,
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
        notes=notes,
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
    except HTTPException:
        job.status = "failed"
        job.error_message = "Backup failed"
        await db.flush()
        raise
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:500]
        await db.flush()
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc


async def list_backups(db: AsyncSession, tenant_id: str, limit: int = 50) -> list[m.BackupJob]:
    result = await db.execute(
        select(m.BackupJob)
        .where(m.BackupJob.tenant_id == tenant_id)
        .order_by(m.BackupJob.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list(result.scalars().all())


async def get_backup(db: AsyncSession, tenant_id: str, backup_id: str) -> m.BackupJob:
    job = await db.get(m.BackupJob, backup_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Backup not found")
    return job


async def read_backup_bytes(job: m.BackupJob) -> bytes:
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Backup is not available for download")
    path = Path(job.storage_path)
    if not path.is_file():
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


async def apply_restore(db: AsyncSession, tenant_id: str, payload: dict) -> dict:
    report = await validate_restore_payload(payload, tenant_id)
    datasets = payload.get("datasets") or {}
    restored: dict[str, int] = {}

    for name, model in DATASET_SPECS:
        rows = datasets.get(name) or []
        count = 0
        for raw in rows:
            data = {k: _parse_value(model, k, v) for k, v in dict(raw).items() if k in model.__table__.columns}
            data["tenant_id"] = tenant_id
            pk = data.get("id")
            if not pk:
                continue
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
                db.add(model(**data))
            count += 1
        restored[name] = count
        await db.flush()

    report["restored"] = restored
    report["applied"] = True
    return report


async def restore_backup(
    db: AsyncSession,
    *,
    tenant_id: str,
    backup_id: str,
    dry_run: bool = True,
    confirm: bool = False,
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
    try:
        report = await apply_restore(db, tenant_id, payload)
        job.status = "completed"
        await db.flush()
        report["dry_run"] = False
        return report
    except Exception:
        job.status = "completed"
        await db.flush()
        raise


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
        path = Path(job.storage_path) if job.storage_path else None
        if path and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
        await db.delete(job)
        removed += 1
    return removed


def ensure_backup_dir_writable() -> None:
    root = backup_root()
    probe = root / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Backup directory not writable: {root}") from exc


async def run_scheduled_backup_if_due(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
) -> dict:
    """Run a backup when schedule is enabled and due. Safe for Celery/cron."""
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
    ensure_backup_dir_writable()
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
