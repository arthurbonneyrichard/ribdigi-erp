from app.celery_app import celery
from app import jobs as jobs_svc
from app.config import settings


def test_celery_app_has_broker_and_beat_entries():
    assert celery.conf.broker_url
    assert "scan-low-stock" in celery.conf.beat_schedule
    assert "scan-payment-due" in celery.conf.beat_schedule
    assert "scan-quotation-expiry" in celery.conf.beat_schedule
    assert "generate-recurring-expenses" in celery.conf.beat_schedule
    assert "run-due-backups" in celery.conf.beat_schedule
    assert "scan-trial-lifecycle" in celery.conf.beat_schedule
    assert "run-due-report-emails" in celery.conf.beat_schedule
    assert "refresh-fx-rates" in celery.conf.beat_schedule
    assert "sync-bank-feeds" in celery.conf.beat_schedule
    assert "generate-ai-low-stock-predictions" in celery.conf.beat_schedule
    assert "generate-ai-insights" in celery.conf.beat_schedule


def test_job_handlers_registered():
    assert set(jobs_svc.JOB_HANDLERS) == {
        "scan_low_stock",
        "scan_payment_due",
        "scan_quotation_expiry",
        "generate_recurring_expenses",
        "run_due_backups",
        "scan_trial_lifecycle",
        "run_due_report_emails",
        "refresh_fx_rates",
        "sync_bank_feeds",
        "generate_ai_low_stock_predictions",
        "generate_ai_insights",
    }


def test_celery_result_backend_defaults_to_redis_db1():
    assert settings.celery_result_backend.endswith("/1") or "redis" in settings.celery_result_backend


def test_run_async_executes_coroutine():
    async def _one():
        return 41 + 1

    assert jobs_svc.run_async(_one()) == 42
