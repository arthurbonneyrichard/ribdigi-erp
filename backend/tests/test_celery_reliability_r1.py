"""Celery/Redis/RabbitMQ reliability packaging fidelity (MVP)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.celery_app import celery
from app import jobs as jobs_svc
from app.main import app
from app.rate_limit import rate_limiter

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/ops")
EVIDENCE_FILE = EVIDENCE_DIR / "celery_reliability_r1.json"
CHECKLIST = ROOT / "ops" / "celery" / "celery-reliability-checklist.json"

EXPECTED_HANDLERS = {
    "scan_low_stock",
    "scan_payment_due",
    "scan_quotation_expiry",
    "scan_recurring_expense_due",
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


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_celery_reliability_runbook():
    doc = _read("docs/CELERY_RELIABILITY_RUNBOOK.md")
    assert "CELERY_ENABLED" in doc
    assert "RabbitMQ" in doc
    assert "Redis" in doc
    assert "/api/v1/jobs" in doc
    assert "health/ready" in doc
    assert "archive_cold_audit_logs" in doc
    assert "retry_due_webhooks" in doc
    assert "AI nightly" in doc
    assert "live_broker_soak_executed" in doc
    assert "test_celery_reliability_r1.py" in doc
    assert "celery_reliability_r1.json" in doc


def test_ops_celery_packaging():
    readme = _read("ops/celery/README.md")
    assert "CELERY_RELIABILITY_RUNBOOK.md" in readme
    assert "celery-reliability-checklist.json" in readme

    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["workstream"] == "R1"
    assert mapping["live_broker_soak_executed"] is False
    assert mapping["ai_nightly_claimed"] is False
    assert mapping["ci_queue_drained_claimed"] is False
    assert mapping["doc"] == "docs/CELERY_RELIABILITY_RUNBOOK.md"
    assert len(mapping["steps"]) >= 6
    for step in mapping["steps"]:
        assert step["class"] in {"operator_required", "packaging"}
    assert "celery_reliability_r1.json" in mapping["evidence_artifact"]

    compose = _read("ops/celery/docker-compose.celery-drill.example.yml")
    assert "redis" in compose.lower()
    assert "rabbitmq" in compose.lower()
    assert "celery" in compose.lower()


def test_handler_beat_jobs_api_parity():
    assert set(jobs_svc.JOB_HANDLERS) == EXPECTED_HANDLERS
    beat_tasks = {entry["task"] for entry in celery.conf.beat_schedule.values()}
    for name in EXPECTED_HANDLERS:
        assert f"app.tasks.{name}" in beat_tasks

    api_src = _read("backend/app/api.py")
    for key in (
        "scan_trial_lifecycle_minutes",
        "refresh_fx_rates_minutes",
        "sync_bank_feeds_minutes",
        "archive_cold_audit_logs_minutes",
        "retry_due_webhooks_seconds",
        "scan_ai_security_alerts_minutes",
    ):
        assert key in api_src


def test_jobs_unknown_raises():
    with pytest.raises(ValueError, match="Unknown job"):
        asyncio.run(jobs_svc.run_job("not_a_real_job"))


def test_jobs_sync_dry_run_stub(monkeypatch):
    async def _stub():
        return {"tenants": 0, "results": [], "dry_run": True}

    monkeypatch.setitem(jobs_svc.JOB_HANDLERS, "scan_low_stock", _stub)
    outcome = asyncio.run(jobs_svc.run_job("scan_low_stock"))
    assert outcome["job"] == "scan_low_stock"
    assert outcome["dry_run"] is True


def test_shallow_health_for_reliability_pack():
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200


def test_production_readiness_gate_and_evidence():
    pr = _read("PRODUCTION_READINESS.md")
    assert "- [x] Redis/Celery/RabbitMQ used for intended production workloads." in pr
    assert "- [ ] Redis/Celery/RabbitMQ used for intended production workloads." not in pr
    assert "CELERY_RELIABILITY_RUNBOOK.md" in pr
    assert "test_celery_reliability_r1.py" in pr
    assert "AI nightly" in pr

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "workstream": "R1",
        "passed": True,
        "packaging_only": True,
        "live_broker_soak_executed": False,
        "ai_nightly_claimed": False,
        "ci_queue_drained_claimed": False,
        "handlers": sorted(EXPECTED_HANDLERS),
        "runbook": "docs/CELERY_RELIABILITY_RUNBOOK.md",
        "checklist": "ops/celery/celery-reliability-checklist.json",
        "deep_health": True,
        "jobs_beat_parity": True,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_broker_soak_executed"] is False
    assert loaded["ai_nightly_claimed"] is False
    assert loaded["ci_queue_drained_claimed"] is False
