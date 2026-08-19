"""Stage 19 R1: Reliability & cache (LAUNCH §5) fidelity."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import cache as cache_svc
from app.celery_app import celery
from app import jobs as jobs_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_BEAT = {
    "scan-low-stock",
    "scan-payment-due",
    "scan-quotation-expiry",
    "generate-recurring-expenses",
    "run-due-backups",
    "run-due-report-emails",
    "refresh-fx-rates",
    "sync-bank-feeds",
    "retry-due-webhooks",
    "generate-ai-low-stock-predictions",
    "generate-ai-insights",
}

REQUIRED_HANDLERS = {
    "scan_low_stock",
    "scan_payment_due",
    "scan_quotation_expiry",
    "generate_recurring_expenses",
    "run_due_backups",
    "run_due_report_emails",
    "refresh_fx_rates",
    "sync_bank_feeds",
    "retry_due_webhooks",
    "generate_ai_low_stock_predictions",
    "generate_ai_insights",
}


class BlipRedis:
    """Redis stand-in that fails mid-request (connection blip)."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.fail_get = False
        self.fail_set = False

    async def ping(self):
        return True

    async def get(self, key: str):
        if self.fail_get:
            raise ConnectionError("redis blip on get")
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        if self.fail_set:
            raise ConnectionError("redis blip on setex")
        self.store[key] = value
        return True

    async def delete(self, *keys: str):
        for key in keys:
            self.store.pop(key, None)
        return len(keys)


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.fixture
def blip_cache(monkeypatch):
    fake = BlipRedis()
    c = cache_svc.app_cache
    c.reset_for_tests()
    c._init_attempted = True
    c._backend = "redis"
    c._redis = fake
    monkeypatch.setattr(cache_svc.settings, "CACHE_ENABLED", True)
    monkeypatch.setattr(cache_svc.settings, "CACHE_BACKEND", "redis")
    monkeypatch.setattr(cache_svc.settings, "CACHE_DASHBOARD_TTL_SECONDS", 300)
    monkeypatch.setattr(cache_svc.settings, "CACHE_CATALOG_TTL_SECONDS", 600)
    monkeypatch.setattr(cache_svc.settings, "CACHE_PERMISSIONS_TTL_SECONDS", 3600)
    monkeypatch.setattr("app.config.settings.CACHE_ENABLED", True)
    yield fake
    c.reset_for_tests()


@pytest.mark.asyncio
async def test_dashboard_catalog_soft_fail_on_redis_blip(client, blip_cache):
    """LAUNCH §5: dashboard/catalog remain 200 when Redis get/set blips."""
    ac, seed = client
    headers = await _super(ac, seed)

    # Warm path works
    ok = await ac.get("/api/v1/dashboard", headers=headers)
    assert ok.status_code == 200, ok.text
    dash_key = cache_svc.app_cache.dashboard_key(seed["t1"].id)
    assert dash_key in blip_cache.store

    # Redis get blip — miss soft-fails to live query
    blip_cache.fail_get = True
    blip_get = await ac.get("/api/v1/dashboard", headers=headers)
    assert blip_get.status_code == 200, blip_get.text
    assert "products" in blip_get.json()["data"]

    # Redis set blip — write soft-fails; response still 200
    blip_cache.fail_get = False
    blip_cache.fail_set = True
    blip_cache.store.clear()
    products = await ac.get("/api/v1/products", headers=headers)
    assert products.status_code == 200, products.text
    assert isinstance(products.json()["data"], list)

    cats = await ac.get("/api/v1/catalog/categories", headers=headers)
    assert cats.status_code == 200, cats.text


@pytest.mark.asyncio
async def test_permissions_invalidate_on_role_and_record_scope(client, blip_cache):
    """LAUNCH §5: permissions cache cleared on role and record_scope change."""
    ac, seed = client
    cashier_headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    warm = await ac.get("/api/v1/me", headers=cashier_headers)
    assert warm.status_code == 200, warm.text
    key = cache_svc.app_cache.permissions_key(seed["t1"].id, seed["u1"].id)
    assert key in blip_cache.store

    admin = await _super(ac, seed)
    role_patch = await ac.patch(
        f"/api/v1/users/{seed['u1'].id}",
        headers=admin,
        json={"role": "sales_officer"},
    )
    assert role_patch.status_code == 200, role_patch.text
    assert key not in blip_cache.store

    rewarm = await ac.get("/api/v1/me", headers=cashier_headers)
    assert rewarm.status_code == 200
    assert key in blip_cache.store

    scope_patch = await ac.patch(
        f"/api/v1/users/{seed['u1'].id}",
        headers=admin,
        json={"record_scope": "branch"},
    )
    assert scope_patch.status_code == 200, scope_patch.text
    assert key not in blip_cache.store

    again = await ac.get("/api/v1/me", headers=cashier_headers)
    assert again.status_code == 200
    assert again.json()["data"]["record_scope"] == "branch"
    assert key in blip_cache.store


def test_celery_beat_schedule_matrix():
    """LAUNCH §5: beat schedule covers reliability job matrix (+ AI)."""
    beat = celery.conf.beat_schedule or {}
    missing = REQUIRED_BEAT - set(beat)
    assert not missing, f"Missing beat entries: {sorted(missing)}"
    handlers_missing = REQUIRED_HANDLERS - set(jobs_svc.JOB_HANDLERS)
    assert not handlers_missing, f"Missing handlers: {sorted(handlers_missing)}"


@pytest.mark.asyncio
async def test_admin_jobs_list_and_dry_run(client, monkeypatch):
    """LAUNCH §5: GET /jobs + POST /jobs/{name}/run operator dry-run."""
    ac, seed = client
    headers = await _super(ac, seed)

    listed = await ac.get("/api/v1/jobs", headers=headers)
    assert listed.status_code == 200, listed.text
    data = listed.json()["data"]
    assert isinstance(data["jobs"], list)
    for name in REQUIRED_HANDLERS:
        assert name in data["jobs"], name
    assert "scan_low_stock_minutes" in data["beat"]

    # Job runners open SessionLocal (Postgres). Stub the handler outcome so the
    # admin HTTP dry-run path is proven without a live broker/DB.
    async def fake_run_job(name: str):
        assert name == "scan_low_stock"
        return {
            "job": name,
            "tenants": 1,
            "results": [{"tenant_id": seed["t1"].id, "ok": True, "result": {"created": 0}}],
        }

    monkeypatch.setattr(jobs_svc, "run_job", fake_run_job)

    ran = await ac.post("/api/v1/jobs/scan_low_stock/run", headers=headers)
    assert ran.status_code == 200, ran.text
    body = ran.json()["data"]
    assert body["job"] == "scan_low_stock"
    assert body["tenants"] == 1
    assert ran.json()["success"] is True

    unknown = await ac.post("/api/v1/jobs/not_a_real_job/run", headers=headers)
    assert unknown.status_code == 404


def test_logical_dr_drill_packaging_documented():
    """LAUNCH §5 / Stage 19 R1: logical DR runbook exists; WAL/PITR out of scope."""
    runbook = ROOT / "docs" / "DR_LOGICAL_BACKUP_RUNBOOK.md"
    assert runbook.is_file()
    text = runbook.read_text(encoding="utf-8")
    assert "dry_run" in text or "Dry-run" in text
    assert "confirm_text" in text and "RESTORE" in text
    assert "WAL" in text or "PITR" in text
    assert "Out of scope" in text or "post-MVP" in text
    assert "test_backup_restore_proof_b1.py" in text


def test_launch_checklist_section5_and_plan_synced():
    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    section = launch.split("## 5. Reliability & cache")[1].split("## 6.")[0]
    assert "[x] Dashboard / catalog cache soft-fails if Redis blips" in section
    assert "[x] Permissions cache invalidates after role / record_scope change" in section
    assert "[x] Celery beat schedules include:" in section
    assert "[x] Admin `GET /jobs` + manual `POST /jobs/{name}/run`" in section
    assert "Stage 19 R1" in section or "test_reliability_cache_r1.py" in section

    plan = (ROOT / "docs" / "STAGE_19_PLAN.md").read_text(encoding="utf-8")
    r1_line = [ln for ln in plan.splitlines() if "| **R1**" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_reliability_cache_r1.py" in plan

    dr = (ROOT / "docs" / "DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "Stage 19" in dr or "logical" in dr.lower()
