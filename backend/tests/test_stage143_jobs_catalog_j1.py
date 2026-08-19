"""Stage 143 J1 — jobs catalog CSV export (broker URLs never included)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import jobs as jobs_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_jobs_catalog_export_csv_secret_free(client):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/jobs/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "job_name" in header and "celery_enabled" in header
    assert "beat_interval_minutes" in header
    for name in ("scan_low_stock", "run_due_backups", "retry_due_webhooks"):
        assert name in jobs_svc.JOB_HANDLERS
        assert name in text
    lower = text.lower()
    assert "broker" not in header.lower()
    assert "result_backend" not in header.lower()
    assert "amqp://" not in lower
    assert "redis://" not in lower
    assert "password" not in lower


def test_jobs_catalog_export_ui_j1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 143" in page
    assert "/jobs/export" in page
    assert "Export jobs catalog CSV" in page
    assert "jobs-catalog" in page
