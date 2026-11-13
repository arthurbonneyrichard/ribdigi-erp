"""Celery application: RabbitMQ broker, Redis results, beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab, schedule

from app.config import settings


def on_the_clock(every_minutes: int, *, minute: int = 0):
    """Run every N minutes at fixed clock times.

    A plain `schedule(run_every=...)` counts from when celery_beat started, and beat restarts on
    every deploy (its schedule file is in /tmp). With a few deploys a day an hourly job such as
    run_due_backups never reached its first run. Clock times survive restarts: hourly jobs run at
    `minute` past every hour, longer ones every few hours on the hour, shorter ones every N minutes.
    """
    n = max(1, int(every_minutes))
    if n < 60 and 60 % n == 0:
        return crontab(minute=f"{minute % n}-59/{n}")
    if n % 60 == 0 and 1440 % n == 0:
        hours = n // 60
        return crontab(minute=minute, hour="0" if hours == 24 else f"*/{hours}")
    return schedule(run_every=n * 60.0)  # an interval that does not fit the clock


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
            "schedule": on_the_clock(settings.CELERY_LOW_STOCK_INTERVAL_MINUTES, minute=7),
        },
        "scan-payment-due": {
            "task": "app.tasks.scan_payment_due",
            "schedule": on_the_clock(settings.CELERY_PAYMENT_DUE_INTERVAL_MINUTES, minute=14),
        },
        "scan-quotation-expiry": {
            "task": "app.tasks.scan_quotation_expiry",
            "schedule": on_the_clock(settings.CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES, minute=21),
        },
        "scan-batch-expiry": {
            "task": "app.tasks.scan_batch_expiry",
            "schedule": on_the_clock(settings.CELERY_BATCH_EXPIRY_INTERVAL_MINUTES, minute=28),
        },
        "scan-recurring-expense-due": {
            "task": "app.tasks.scan_recurring_expense_due",
            "schedule": on_the_clock(settings.CELERY_RECURRING_NOTIFY_INTERVAL_MINUTES, minute=35),
        },
        "generate-recurring-expenses": {
            "task": "app.tasks.generate_recurring_expenses",
            "schedule": on_the_clock(settings.CELERY_RECURRING_INTERVAL_MINUTES, minute=42),
        },
        "run-due-backups": {
            "task": "app.tasks.run_due_backups",
            "schedule": on_the_clock(settings.CELERY_BACKUP_INTERVAL_MINUTES, minute=5),
        },
        "scan-trial-lifecycle": {
            "task": "app.tasks.scan_trial_lifecycle",
            "schedule": on_the_clock(settings.CELERY_TRIAL_INTERVAL_MINUTES, minute=49),
        },
        "run-due-report-emails": {
            "task": "app.tasks.run_due_report_emails",
            "schedule": on_the_clock(settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES, minute=56),
        },
        "refresh-fx-rates": {
            "task": "app.tasks.refresh_fx_rates",
            "schedule": on_the_clock(settings.CELERY_FX_INTERVAL_MINUTES, minute=3),
        },
        "sync-bank-feeds": {
            "task": "app.tasks.sync_bank_feeds",
            "schedule": on_the_clock(settings.CELERY_BANK_FEED_INTERVAL_MINUTES, minute=10),
        },
        "archive-cold-audit-logs": {
            "task": "app.tasks.archive_cold_audit_logs",
            "schedule": on_the_clock(settings.CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES, minute=17),
        },
        "retry-due-webhooks": {
            "task": "app.tasks.retry_due_webhooks",
            "schedule": schedule(
                run_every=max(5, int(settings.CELERY_WEBHOOK_RETRY_INTERVAL_SECONDS))
            ),
        },
        "scan-ai-security-alerts": {
            "task": "app.tasks.scan_ai_security_alerts",
            "schedule": on_the_clock(settings.CELERY_AI_SECURITY_INTERVAL_MINUTES, minute=24),
        },
        "scan-hr-escalations": {
            "task": "app.tasks.scan_hr_escalations",
            "schedule": crontab(minute=30, hour=7),
        },
        "send-weekly-ai-insight-digest": {
            "task": "app.tasks.send_weekly_ai_insight_digest",
            "schedule": crontab(minute=0, hour=7, day_of_week="monday"),
        },
        "process-subscription-renewals": {
            "task": "app.tasks.process_subscription_renewals",
            "schedule": on_the_clock(settings.CELERY_BILLING_INTERVAL_MINUTES, minute=31),
        },
        "expire-ecommerce-reservations": {
            "task": "app.tasks.expire_ecommerce_reservations",
            "schedule": on_the_clock(settings.CELERY_ECOMMERCE_INTERVAL_MINUTES, minute=38),
        },
        "sync-ecommerce-connectors": {
            "task": "app.tasks.sync_ecommerce_connectors",
            "schedule": on_the_clock(settings.CELERY_ECOMMERCE_INTERVAL_MINUTES, minute=45),
        },
        "sample-server-health": {
            "task": "app.tasks.sample_server_health",
            "schedule": schedule(run_every=60.0),
        },
        "deliver-support-outbox": {
            "task": "app.tasks.deliver_support_outbox",
            "schedule": schedule(run_every=60.0),
        },
    },
)
