"""Admin Jobs console API + FE packaging (Celery reliability UX)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import jobs as jobs_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_jobs_list_and_run_sync(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)

    listed = await ac.get("/api/v1/jobs", headers=admin)
    assert listed.status_code == 200, listed.text
    data = listed.json()["data"]
    assert "jobs" in data
    assert "beat" in data
    assert "celery_enabled" in data
    for name in jobs_svc.JOB_HANDLERS:
        assert name in data["jobs"]

    # Prefer a lightweight handler for sync run.
    name = "scan_quotation_expiry"
    assert name in data["jobs"]
    ran = await ac.post(f"/api/v1/jobs/{name}/run", headers=admin, json={})
    assert ran.status_code == 200, ran.text
    body = ran.json()["data"]
    assert body.get("job") == name


def test_jobs_console_fe_packaged():
    page = (ROOT / "frontend/app/jobs/page.tsx").read_text(encoding="utf-8")
    assert "/jobs" in page
    assert "Run sync" in page
    assert "Enqueue" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "['Jobs', '/jobs', 'jobs']" in shell
    runbook = (ROOT / "docs/CELERY_RELIABILITY_RUNBOOK.md").read_text(encoding="utf-8")
    assert "/jobs" in runbook
    assert "Jobs console" in runbook or "frontend/app/jobs" in runbook
