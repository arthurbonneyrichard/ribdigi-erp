"""Celery application: RabbitMQ broker, Redis results, beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from app.config import settings

celery = Celery(
    "ribdigi",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_always_eager=bool(settings.CELERY_TASK_ALWAYS_EAGER),
    task_eager_propagates=True,
    beat_schedule={
        "scan-low-stock": {
            "task": "app.tasks.scan_low_stock",
            "schedule": schedule(run_every=max(1, int(settings.CELERY_LOW_STOCK_INTERVAL_MINUTES)) * 60.0),
        },
        "scan-payment-due": {
            "task": "app.tasks.scan_payment_due",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_PAYMENT_DUE_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "scan-quotation-expiry": {
            "task": "app.tasks.scan_quotation_expiry",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "generate-recurring-expenses": {
            "task": "app.tasks.generate_recurring_expenses",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_RECURRING_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "run-due-backups": {
            "task": "app.tasks.run_due_backups",
            "schedule": schedule(run_every=max(1, int(settings.CELERY_BACKUP_INTERVAL_MINUTES)) * 60.0),
        },
        "scan-trial-lifecycle": {
            "task": "app.tasks.scan_trial_lifecycle",
            "schedule": schedule(run_every=max(1, int(settings.CELERY_TRIAL_INTERVAL_MINUTES)) * 60.0),
        },
        "run-due-report-emails": {
            "task": "app.tasks.run_due_report_emails",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "refresh-fx-rates": {
            "task": "app.tasks.refresh_fx_rates",
            "schedule": schedule(run_every=max(1, int(settings.CELERY_FX_INTERVAL_MINUTES)) * 60.0),
        },
        "sync-bank-feeds": {
            "task": "app.tasks.sync_bank_feeds",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_BANK_FEED_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "generate-ai-low-stock-predictions": {
            "task": "app.tasks.generate_ai_low_stock_predictions",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_AI_PREDICTION_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "generate-ai-insights": {
            "task": "app.tasks.generate_ai_insights",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_AI_INSIGHTS_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "archive-cold-audit-logs": {
            "task": "app.tasks.archive_cold_audit_logs",
            "schedule": schedule(
                run_every=max(1, int(settings.CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES)) * 60.0
            ),
        },
        "retry-due-webhooks": {
            "task": "app.tasks.retry_due_webhooks",
            "schedule": schedule(
                run_every=max(5, int(settings.CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS))
            ),
        },
    },
)
