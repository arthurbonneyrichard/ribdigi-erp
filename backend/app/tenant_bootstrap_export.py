"""CSV export for company profile, jobs catalog, and onboarding checklist (Stage 143). Secrets excluded."""

from __future__ import annotations

import csv
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app import jobs as jobs_svc
from app import onboarding as onboarding_svc
from app import tenants as tenants_svc
from app.config import settings as app_settings
from app.session_passkey_doc_export import _cell

COMPANY_PROFILE_EXPORT_COLUMNS = [
    "id",
    "slug",
    "company_name",
    "legal_name",
    "registration_number",
    "industry",
    "currency",
    "tax_jurisdiction",
    "tax_registration_number",
    "tax_filing_period",
    "status",
    "plan_code",
    "billing_deferred",
    "phone",
    "email",
    "website",
    "address",
    "billing_address",
    "shipping_address",
    "warehouse_address",
    "contact_person_name",
    "contact_person_email",
    "contact_person_phone",
    "inactivity_timeout_minutes",
    "date_format",
    "number_format",
    "time_format",
    "timezone",
    "fiscal_year_start",
    "has_logo",
    "trial_ends_at",
    "grace_ends_at",
    "days_remaining",
    "read_only",
    "created_at",
]

JOBS_CATALOG_EXPORT_COLUMNS = [
    "job_name",
    "beat_interval_minutes",
    "celery_enabled",
    "task_always_eager",
]

# Beat schedule keys in GET /jobs → matching JOB_HANDLERS names
_JOB_BEAT_KEYS = {
    "scan_low_stock": "scan_low_stock_minutes",
    "scan_payment_due": "scan_payment_due_minutes",
    "scan_quotation_expiry": "scan_quotation_expiry_minutes",
    "generate_recurring_expenses": "generate_recurring_expenses_minutes",
    "run_due_backups": "run_due_backups_minutes",
    "run_due_report_emails": "run_due_report_emails_minutes",
    "generate_ai_low_stock_predictions": "generate_ai_low_stock_predictions_minutes",
    "generate_ai_insights": "generate_ai_insights_minutes",
    "archive_cold_audit_logs": "archive_cold_audit_logs_minutes",
}

ONBOARDING_CHECKLIST_EXPORT_COLUMNS = [
    "step_id",
    "title",
    "description",
    "href",
    "completed",
    "auto_completed",
    "skipped",
    "completed_count",
    "total_count",
    "progress_pct",
    "dismissed",
    "visible",
]


async def export_company_profile_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 143 P1 — company profile snapshot CSV (no secrets / no billing Complete claim)."""
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    data = tenants_svc.serialize_tenant(tenant)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COMPANY_PROFILE_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in COMPANY_PROFILE_EXPORT_COLUMNS})
    return buf.getvalue()


def export_jobs_catalog_csv() -> str:
    """Stage 143 J1 — Celery job catalog + beat intervals; never include broker/result URLs."""
    beat = {
        "scan_low_stock_minutes": app_settings.CELERY_LOW_STOCK_INTERVAL_MINUTES,
        "scan_payment_due_minutes": app_settings.CELERY_PAYMENT_DUE_INTERVAL_MINUTES,
        "scan_quotation_expiry_minutes": app_settings.CELERY_QUOTATION_EXPIRY_INTERVAL_MINUTES,
        "generate_recurring_expenses_minutes": app_settings.CELERY_RECURRING_INTERVAL_MINUTES,
        "run_due_backups_minutes": app_settings.CELERY_BACKUP_INTERVAL_MINUTES,
        "run_due_report_emails_minutes": app_settings.CELERY_REPORT_EMAIL_INTERVAL_MINUTES,
        "generate_ai_low_stock_predictions_minutes": app_settings.CELERY_AI_PREDICTION_INTERVAL_MINUTES,
        "generate_ai_insights_minutes": app_settings.CELERY_AI_INSIGHTS_INTERVAL_MINUTES,
        "archive_cold_audit_logs_minutes": app_settings.CELERY_AUDIT_ARCHIVE_INTERVAL_MINUTES,
    }
    celery_enabled = bool(app_settings.CELERY_ENABLED)
    eager = bool(app_settings.CELERY_TASK_ALWAYS_EAGER)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=JOBS_CATALOG_EXPORT_COLUMNS)
    writer.writeheader()
    for name in sorted(jobs_svc.JOB_HANDLERS.keys()):
        beat_key = _JOB_BEAT_KEYS.get(name)
        interval = beat.get(beat_key) if beat_key else None
        writer.writerow(
            {
                "job_name": _cell(name),
                "beat_interval_minutes": _cell(interval),
                "celery_enabled": _cell(celery_enabled),
                "task_always_eager": _cell(eager),
            }
        )
    return buf.getvalue()


async def export_onboarding_checklist_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 143 O1 — onboarding checklist step rows with progress summary columns."""
    data = await onboarding_svc.build_checklist(db, tenant_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ONBOARDING_CHECKLIST_EXPORT_COLUMNS)
    writer.writeheader()
    for step in data.get("steps") or []:
        writer.writerow(
            {
                "step_id": _cell(step.get("id")),
                "title": _cell(step.get("title")),
                "description": _cell(step.get("description")),
                "href": _cell(step.get("href")),
                "completed": _cell(bool(step.get("completed"))),
                "auto_completed": _cell(bool(step.get("auto_completed"))),
                "skipped": _cell(bool(step.get("skipped"))),
                "completed_count": _cell(data.get("completed_count")),
                "total_count": _cell(data.get("total_count")),
                "progress_pct": _cell(data.get("progress_pct")),
                "dismissed": _cell(bool(data.get("dismissed"))),
                "visible": _cell(bool(data.get("visible"))),
            }
        )
    return buf.getvalue()
