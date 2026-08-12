"""Celery tasks wrapping async multi-tenant jobs."""

from __future__ import annotations

from app.celery_app import celery
from app.config import settings
from app import jobs as jobs_svc


@celery.task(name="app.tasks.scan_low_stock")
def scan_low_stock() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_low_stock())


@celery.task(name="app.tasks.scan_payment_due")
def scan_payment_due() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_payment_due())


@celery.task(name="app.tasks.generate_recurring_expenses")
def generate_recurring_expenses() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_generate_recurring_expenses())


@celery.task(name="app.tasks.run_due_backups")
def run_due_backups() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_run_due_backups())


@celery.task(name="app.tasks.scan_trial_lifecycle")
def scan_trial_lifecycle() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_trial_lifecycle())


@celery.task(name="app.tasks.run_due_report_emails")
def run_due_report_emails() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_run_due_report_emails())


@celery.task(name="app.tasks.refresh_fx_rates")
def refresh_fx_rates() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_refresh_fx_rates())


@celery.task(name="app.tasks.sync_bank_feeds")
def sync_bank_feeds() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_sync_bank_feeds())


@celery.task(name="app.tasks.archive_cold_audit_logs")
def archive_cold_audit_logs() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_archive_cold_audit_logs())


@celery.task(name="app.tasks.retry_due_webhooks")
def retry_due_webhooks() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_retry_due_webhooks())


@celery.task(name="app.tasks.run_named_job")
def run_named_job(name: str) -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.run_job(name))
