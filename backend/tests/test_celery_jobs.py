from app.celery_app import celery
from app import jobs as jobs_svc
from app.config import settings


EXPECTED_HANDLERS = {
    "scan_low_stock",
    "scan_payment_due",
    "scan_quotation_expiry",
    "generate_recurring_expenses",
    "run_due_backups",
    "scan_trial_lifecycle",
    "run_due_report_emails",
    "refresh_fx_rates",
    "sync_bank_feeds",
    "archive_cold_audit_logs",
    "retry_due_webhooks",
    "scan_ai_security_alerts",
}

EXPECTED_BEAT = {
    "scan-low-stock",
    "scan-payment-due",
    "scan-quotation-expiry",
    "generate-recurring-expenses",
    "run-due-backups",
    "scan-trial-lifecycle",
    "run-due-report-emails",
    "refresh-fx-rates",
    "sync-bank-feeds",
    "archive-cold-audit-logs",
    "retry-due-webhooks",
    "scan-ai-security-alerts",
}


def test_celery_app_has_broker_and_beat_entries():
    assert celery.conf.broker_url
    assert EXPECTED_BEAT.issubset(set(celery.conf.beat_schedule.keys()))


def test_job_handlers_registered():
    assert set(jobs_svc.JOB_HANDLERS) == EXPECTED_HANDLERS


def test_beat_entries_match_handlers():
    """Beat task names use dotted module paths; handler keys use underscores."""
    beat_tasks = {entry["task"] for entry in celery.conf.beat_schedule.values()}
    for name in EXPECTED_HANDLERS:
        assert f"app.tasks.{name}" in beat_tasks


def test_celery_result_backend_defaults_to_redis_db1():
    assert settings.celery_result_backend.endswith("/1") or "redis" in settings.celery_result_backend


def test_run_async_executes_coroutine():
    async def _one():
        return 41 + 1

    assert jobs_svc.run_async(_one()) == 42


def test_run_async_reuses_worker_loop():
    """Second call must not fail with 'Future attached to a different loop'."""

    async def _two():
        return 2

    assert jobs_svc.run_async(_two()) == 2
    assert jobs_svc.run_async(_two()) == 2

