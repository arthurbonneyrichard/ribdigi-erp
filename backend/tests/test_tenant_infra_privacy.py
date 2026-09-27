"""Tenant ERP must not expose storage, deploy, or infrastructure diagnostics."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

SECRETISH = re.compile(
    r"(?i)(s3_secret|s3_access_key|minioadmin|amqp://|redis://|postgresql(\+asyncpg)?://|"
    r"celery_broker|STORAGE_BACKEND|S3_BUCKET|RIBDIGI_BUILD|release_channel|"
    r"rabbitmq|MEDIA_DIR|/data/media)"
)


async def _company_admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _platform_owner(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tenant_cannot_view_storage_configuration(client):
    ac, _seed = client
    admin = await _company_admin(ac)
    cashier = await _cashier(ac)

    for headers in (admin, cashier):
        r = await ac.get("/api/v1/settings/storage", headers=headers)
        assert r.status_code == 403, r.text
        blob = r.text.lower()
        assert "minio" not in blob
        assert "s3_bucket" not in blob
        assert "media_dir" not in blob
        assert "/data/media" not in blob


@pytest.mark.asyncio
async def test_tenant_cannot_access_deploy_infra_diagnostics(client, monkeypatch):
    ac, seed = client
    admin = await _company_admin(ac)
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)

    deep = await ac.get("/api/v1/health?deep=true", headers=admin)
    assert deep.status_code == 200, deep.text
    data = deep.json()["data"]
    assert "checks" not in data
    assert "build_id" not in data
    assert "release_channel" not in data
    assert data.get("message") == "System is operating normally."

    plat = await ac.get("/api/v1/platform/health", headers=admin)
    assert plat.status_code == 403, plat.text
    assert "redis" not in plat.text.lower()

    jobs = await ac.get("/api/v1/jobs", headers=admin)
    assert jobs.status_code == 403, jobs.text
    assert "amqp://" not in jobs.text
    assert "redis://" not in jobs.text

    run = await ac.post("/api/v1/jobs/scan_quotation_expiry/run", headers=admin, json={})
    assert run.status_code == 403, run.text


@pytest.mark.asyncio
async def test_secrets_never_in_tenant_apis(client):
    ac, _seed = client
    admin = await _company_admin(ac)
    paths = [
        "/api/v1/health",
        "/api/v1/health?deep=true",
        "/api/v1/health/ready",
        "/api/v1/tenants/me",
        "/api/v1/me",
        "/api/v1/settings/email",
        "/api/v1/settings/print",
        "/api/v1/backup/settings",
    ]
    for path in paths:
        r = await ac.get(path, headers=admin)
        assert r.status_code in {200, 404}, f"{path} {r.status_code} {r.text[:200]}"
        assert not SECRETISH.search(r.text), f"secret-like payload on {path}: {r.text[:400]}"

    denied = await ac.get("/api/v1/settings/storage", headers=admin)
    assert denied.status_code == 403
    assert not SECRETISH.search(denied.text)

    company = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "/settings/storage" not in company
    assert "Media storage" not in company


@pytest.mark.asyncio
async def test_unauthorized_infra_routes_are_403_or_404(client):
    ac, _seed = client
    admin = await _company_admin(ac)
    cashier = await _cashier(ac)

    anon_jobs = await ac.get("/api/v1/jobs")
    assert anon_jobs.status_code in {401, 403, 404}

    anon_storage = await ac.get("/api/v1/settings/storage")
    assert anon_storage.status_code in {401, 403, 404}

    anon_plat = await ac.get("/api/v1/platform/health")
    assert anon_plat.status_code in {401, 403, 404}

    for headers in (admin, cashier):
        r = await ac.get("/api/v1/settings/storage", headers=headers)
        assert r.status_code in {403, 404}
        r = await ac.get("/api/v1/jobs", headers=headers)
        assert r.status_code in {403, 404}
        r = await ac.get("/api/v1/platform/health", headers=headers)
        assert r.status_code in {403, 404}


@pytest.mark.asyncio
async def test_platform_owner_diagnostics_still_work(client, monkeypatch):
    ac, seed = client
    ops = await _platform_owner(ac, seed)
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setattr("app.health.settings.RATE_LIMIT_REQUIRE_REDIS", False)

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1, "required": False}

    monkeypatch.setattr("app.health.check_redis", _redis_ok)

    plat = await ac.get("/api/v1/platform/health", headers=ops)
    assert plat.status_code == 200, plat.text
    pdata = plat.json()["data"]
    assert pdata["deep"] is True
    assert "checks" in pdata
    assert pdata["checks"]["database"]["status"] == "ok"
    assert "build_id" in pdata

    authed_deep = await ac.get("/api/v1/health?deep=true", headers=ops)
    assert authed_deep.status_code == 200, authed_deep.text
    assert authed_deep.json()["data"]["checks"]["database"]["status"] == "ok"

    storage = await ac.get("/api/v1/settings/storage", headers=ops)
    assert storage.status_code == 200, storage.text
    assert storage.json()["data"]["backend"] in {"local", "s3"}

    jobs = await ac.get("/api/v1/jobs", headers=ops)
    assert jobs.status_code == 200, jobs.text
    assert "jobs" in jobs.json()["data"]
    ran = await ac.post("/api/v1/jobs/scan_quotation_expiry/run", headers=ops, json={})
    assert ran.status_code == 200, ran.text


@pytest.mark.asyncio
async def test_tenant_error_responses_safe(client, monkeypatch):
    ac, seed = client
    admin = await _company_admin(ac)

    async def _db_down(_factory):
        return {
            "status": "error",
            "latency_ms": 1.0,
            "error": "OperationalError",
            "required": True,
        }

    monkeypatch.setattr("app.health.check_database", _db_down)
    ready = await ac.get("/api/v1/health/ready", headers=admin)
    assert ready.status_code == 503
    assert "OperationalError" not in ready.text
    assert "postgres" not in ready.text.lower()
    assert ready.json()["data"]["message"] == "System is temporarily unavailable."

    denied = await ac.post("/api/v1/jobs/scan_quotation_expiry/run", headers=admin, json={})
    assert denied.status_code == 403
    detail = denied.json().get("detail")
    blob = json.dumps(detail) if not isinstance(detail, str) else detail
    assert "CELERY" not in blob
    assert "amqp" not in blob.lower()
    assert "traceback" not in blob.lower()
