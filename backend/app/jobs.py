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


def run_async(coro: Awaitable[Any]) -> Any:
    """Run an async coroutine from a sync Celery worker process."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Should not happen in standard Celery workers; fall back to a new loop in a thread.
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
        return await notifications_svc.scan_quotation_expiry(db, tenant_id)

    return await _for_each_tenant(work)


async def job_generate_recurring_expenses() -> dict:
    from app import expenses as expenses_svc
    from app import notifications as notifications_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        upcoming = await notifications_svc.scan_recurring_expense_upcoming(db, tenant_id)
        created = await expenses_svc.generate_due_recurring(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )
        return {
            "notified": int(upcoming.get("reminded") or 0),
            "created": len(created),
            "expense_ids": [e.id for e in created],
        }

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


async def job_generate_ai_low_stock_predictions() -> dict:
    from app import ai_inventory as ai_inventory_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await ai_inventory_svc.notify_predicted_stockouts(db, tenant_id)

    return await _for_each_tenant(work)


async def job_generate_ai_insights() -> dict:
    from app import ai_insights as ai_insights_svc
    from app.bi_service import scan_tenant_business_insights

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        ai = await ai_insights_svc.publish_insights(db, tenant_id)
        bi = await scan_tenant_business_insights(db, tenant_id)
        return {**ai, "business_intelligence": bi}

    return await _for_each_tenant(work)


async def job_archive_cold_audit_logs() -> dict:
    from app import audit as audit_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await audit_svc.archive_cold_logs(
            db, tenant_id=tenant_id, user_id=SYSTEM_USER_ID
        )

    return await _for_each_tenant(work)


async def job_retry_due_webhooks() -> dict:
    """Stage 7 W2 — re-attempt pending_retry webhook deliveries that are due."""
    from app import webhooks as webhooks_svc

    async def work(db: AsyncSession, tenant_id: str) -> dict:
        return await webhooks_svc.process_due_retries(db, tenant_id=tenant_id)

    return await _for_each_tenant(work)


JOB_HANDLERS: dict[str, Callable[[], Awaitable[dict]]] = {
    "scan_low_stock": job_scan_low_stock,
    "scan_payment_due": job_scan_payment_due,
    "scan_quotation_expiry": job_scan_quotation_expiry,
    "generate_recurring_expenses": job_generate_recurring_expenses,
    "run_due_backups": job_run_due_backups,
    "scan_trial_lifecycle": job_scan_trial_lifecycle,
    "run_due_report_emails": job_run_due_report_emails,
    "refresh_fx_rates": job_refresh_fx_rates,
    "sync_bank_feeds": job_sync_bank_feeds,
    "generate_ai_low_stock_predictions": job_generate_ai_low_stock_predictions,
    "generate_ai_insights": job_generate_ai_insights,
    "archive_cold_audit_logs": job_archive_cold_audit_logs,
    "retry_due_webhooks": job_retry_due_webhooks,
}


async def run_job(name: str) -> dict:
    handler = JOB_HANDLERS.get(name)
    if not handler:
        raise ValueError(f"Unknown job: {name}")
    outcome = await handler()
    return {"job": name, **outcome}
