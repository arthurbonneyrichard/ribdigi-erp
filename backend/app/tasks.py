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


@celery.task(name="app.tasks.scan_quotation_expiry")
def scan_quotation_expiry() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_quotation_expiry())


@celery.task(name="app.tasks.scan_batch_expiry")
def scan_batch_expiry() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_batch_expiry())


@celery.task(name="app.tasks.scan_recurring_expense_due")
def scan_recurring_expense_due() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_recurring_expense_due())


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


@celery.task(name="app.tasks.scan_ai_security_alerts")
def scan_ai_security_alerts() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_scan_ai_security_alerts())


@celery.task(name="app.tasks.send_weekly_ai_insight_digest")
def send_weekly_ai_insight_digest() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_send_weekly_ai_insight_digest())


@celery.task(name="app.tasks.process_subscription_renewals")
def process_subscription_renewals() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_process_subscription_renewals())


@celery.task(name="app.tasks.expire_ecommerce_reservations")
def expire_ecommerce_reservations() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_expire_ecommerce_reservations())


@celery.task(name="app.tasks.sync_ecommerce_connectors")
def sync_ecommerce_connectors() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.job_sync_ecommerce_connectors())


@celery.task(name="app.tasks.deliver_support_outbox")
def deliver_support_outbox() -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    from app.support_tickets import deliver_outbox_job

    return jobs_svc.run_async(deliver_outbox_job())


@celery.task(name="app.tasks.run_named_job")
def run_named_job(name: str) -> dict:
    if not settings.CELERY_ENABLED:
        return {"skipped": True, "reason": "CELERY_ENABLED=false"}
    return jobs_svc.run_async(jobs_svc.run_job(name))
