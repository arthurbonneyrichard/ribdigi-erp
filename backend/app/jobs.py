"""Multi-tenant scheduled job runners (used by Celery and admin triggers)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.db import SessionLocal

logger = logging.getLogger(__name__)

ACTIVE_TENANT_STATUSES = frozenset({"trial", "active"})
SYSTEM_USER_ID = "system"

# Prefer one event loop per Celery worker process so the shared async SQLAlchemy
# engine is not rebound across asyncio.run() cycles (different-loop Futures).
_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async(coro: Awaitable[Any]) -> Any:
    """Run an async coroutine from a sync Celery worker process."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        global _worker_loop
        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_worker_loop)
        return _worker_loop.run_until_complete(coro)
    # Nested running loop (unusual in Celery) — run on a fresh loop in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def list_active_tenant_ids(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(
            select(m.Tenant.id).where(
                m.Tenant.status.in_(list(ACTIVE_TENANT_STATUSES)),
                m.Tenant.suspended_at.is_(None),
            )
        )
    ).scalars().all()
    return list(rows)


async def _for_each_tenant(
    work: Callable[[AsyncSession, str], Awaitable[dict | int | list]],
) -> dict[str, Any]:
    results: list[Any] = []
    async with SessionLocal() as db:
        tenant_ids = await list_active_tenant_ids(db)
        for tenant_id in tenant_ids:
            try:
                outcome = await work(db, tenant_id)
                await db.commit()
                results.append({"tenant_id": tenant_id, "ok": True, "result": outcome})
            except Exception as exc:  # noqa: BLE001 — isolate tenant failures in batch jobs
                logger.exception("Scheduled job failed for tenant %s", tenant_id)
                await db.rollback()
                results.append({"tenant_id": tenant_id, "ok": False, "error": str(exc)})
    return {"tenants": len(results), "results": results}


async def job_scan_low_stock() -> dict:
    from app import notifications as notifications_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        created = await notifications_svc.scan_low_stock(db, tenant_id)
        return {"created": created}

    return await _for_each_tenant(work)


async def job_scan_payment_due() -> dict:
    from app import notifications as notifications_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        created = await notifications_svc.scan_payment_due(db, tenant_id)
        return {"created": created}

    return await _for_each_tenant(work)


async def job_scan_quotation_expiry() -> dict:
    from app import notifications as notifications_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        created = await notifications_svc.scan_quotation_expiry(db, tenant_id)
        return {"created": created}

    return await _for_each_tenant(work)


async def job_scan_recurring_expense_due() -> dict:
    from app import notifications as notifications_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        created = await notifications_svc.scan_recurring_expense_due(db, tenant_id)
        return {"created": created}

    return await _for_each_tenant(work)


async def job_generate_recurring_expenses() -> dict:
    from app import expenses as expenses_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        created = await expenses_svc.generate_due_recurring(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )
        return {"created": len(created), "expense_ids": [e.id for e in created]}

    return await _for_each_tenant(work)


async def job_run_due_backups() -> dict:
    from app import backup as backup_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await backup_svc.run_scheduled_backup_if_due(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )

    return await _for_each_tenant(work)


async def job_scan_trial_lifecycle() -> dict:
    from app import tenants as tenants_svc

    async with SessionLocal() as db:
        try:
            outcome = await tenants_svc.process_trial_lifecycle(db)
            await db.commit()
            return {"ok": True, **outcome}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Trial lifecycle job failed")
            await db.rollback()
            return {"ok": False, "error": str(exc)}


async def job_run_due_report_emails() -> dict:
    from app import report_schedules as report_schedules_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await report_schedules_svc.run_due_schedules_for_tenant(db, tenant_id)

    return await _for_each_tenant(work)


async def job_refresh_fx_rates() -> dict:
    from app import fx as fx_svc
    from app.config import settings

    if (settings.FX_PROVIDER or "").strip().lower() in {"disabled", "off", "none"}:
        return {"skipped": True, "reason": "FX_PROVIDER disabled"}

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        tenant = (
            await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
        ).scalar_one()
        if not bool(getattr(tenant, "fx_auto_refresh", True)):
            return {"skipped": True, "reason": "fx_auto_refresh=false"}
        return await fx_svc.refresh_tenant_rates(db, tenant_id=tenant_id, create_missing=False)

    return await _for_each_tenant(work)


async def job_sync_bank_feeds() -> dict:
    from app import bank_connectors as bank_connectors_svc
    from app.config import settings

    if not bool(settings.BANK_FEED_SYNC_ENABLED):
        return {"skipped": True, "reason": "BANK_FEED_SYNC_ENABLED=false"}

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await bank_connectors_svc.sync_tenant_auto_connections(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )

    return await _for_each_tenant(work)


async def job_archive_cold_audit_logs() -> dict:
    from app import audit as audit_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await audit_svc.archive_cold_logs(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )

    return await _for_each_tenant(work)


async def job_retry_due_webhooks() -> dict:
    """Re-attempt pending_retry webhook deliveries that are due (BR-18.6)."""
    from app import webhooks as webhooks_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await webhooks_svc.process_due_retries(db, tenant_id=tenant_id)

    return await _for_each_tenant(work)


async def job_scan_ai_security_alerts() -> dict:
    """Rule-based AI Security Monitor scan (BR-21.10)."""
    from app import ai_security as ai_security_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        summary = await ai_security_svc.scan_tenant(
            db, tenant_id=tenant_id, actor_user_id=SYSTEM_USER_ID, notify=True
        )
        return {
            "created": summary.get("created", 0),
            "updated": summary.get("updated", 0),
            "notified": summary.get("notified", 0),
            "enabled": summary.get("enabled", False),
        }

    return await _for_each_tenant(work)


JOB_HANDLERS: dict[str, Callable[[], Awaitable[dict]]] = {
    "scan_low_stock": job_scan_low_stock,
    "scan_payment_due": job_scan_payment_due,
    "scan_quotation_expiry": job_scan_quotation_expiry,
    "scan_recurring_expense_due": job_scan_recurring_expense_due,
    "generate_recurring_expenses": job_generate_recurring_expenses,
    "run_due_backups": job_run_due_backups,
    "scan_trial_lifecycle": job_scan_trial_lifecycle,
    "run_due_report_emails": job_run_due_report_emails,
    "refresh_fx_rates": job_refresh_fx_rates,
    "sync_bank_feeds": job_sync_bank_feeds,
    "archive_cold_audit_logs": job_archive_cold_audit_logs,
    "retry_due_webhooks": job_retry_due_webhooks,
    "scan_ai_security_alerts": job_scan_ai_security_alerts,
}


async def run_job(name: str) -> dict:
    handler = JOB_HANDLERS.get(name)
    if not handler:
        raise ValueError(f"Unknown job: {name}")
    outcome = await handler()
    return {"job": name, **outcome}
