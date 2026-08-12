"""Stage 26 C1 — certified load / capacity evidence (CI profiles; not 1000-VU)."""

from __future__ import annotations

import json
from pathlib import Path

import pyotp
import pytest
from httpx import ASGITransport

from app.main import app
from loadtest.config import TARGETS
from loadtest.runner import run_baseline

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/loadtest")
EVIDENCE_FILE = EVIDENCE_DIR / "stage26_c1_capacity_evidence.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_c1_capacity_evidence_artifact(client, db_session):
    """Smoke + CI capacity profiles via ASGI; durable Stage 26 C1 evidence JSON."""
    _ac, seed = client
    from app import catalog_meta as catalog_meta_svc

    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    transport = ASGITransport(app=app)

    smoke = await run_baseline(
        base_url="http://test",
        scenarios="health",
        concurrency=TARGETS.smoke_concurrency,
        iterations=TARGETS.smoke_iterations,
        transport=transport,
        max_error_rate=TARGETS.smoke_max_error_rate,
        max_p95_ms=TARGETS.smoke_p95_ms,
    )
    assert smoke.passed, smoke.failures

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    capacity = await run_baseline(
        base_url="http://test",
        scenarios=TARGETS.ci_capacity_scenarios,
        concurrency=TARGETS.ci_capacity_concurrency,
        iterations=TARGETS.ci_capacity_iterations,
        transport=transport,
        email="super@alpha.example.com",
        password="SecurePass123!",
        tenant_slug="alpha",
        totp_code=code,
        max_error_rate=TARGETS.ci_capacity_max_error_rate,
        max_p95_ms=TARGETS.ci_capacity_p95_ms,
    )
    assert capacity.passed, capacity.to_dict()
    for name in ("health", "login", "products", "dashboard"):
        assert name in capacity.scenarios
        assert capacity.scenarios[name].errors == 0

    payload = {
        "stage": "26",
        "workstream": "C1",
        "passed": True,
        "profiles": {
            "smoke": {
                "tier": "ci_smoke",
                "transport": "asgi",
                **smoke.to_dict(),
            },
            "ci_capacity": {
                "tier": "ci_capacity",
                "transport": "asgi",
                **capacity.to_dict(),
            },
        },
        "targets_doc": "docs/LOAD_TEST_BASELINE.md",
        "mvp_doc": "docs/LOAD_CAPACITY_MVP.md",
        "harness": "backend/loadtest/",
        "operator_1000vu_required": True,
        "staging_locust_deferred": True,
        "stage18_smoke_artifact": "stage18_t1_baseline_smoke.json",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["operator_1000vu_required"] is True
    assert loaded["profiles"]["ci_capacity"]["passed"] is True
    assert loaded["profiles"]["smoke"]["passed"] is True


def test_ci_capacity_targets_and_cli_flag():
    assert TARGETS.ci_capacity_concurrency >= TARGETS.smoke_concurrency
    assert TARGETS.ci_capacity_p95_ms >= TARGETS.smoke_p95_ms  # ASGI-honest (login bcrypt)
    assert TARGETS.staging_p95_ms == 500.0  # operator staging target unchanged
    assert "login" in TARGETS.ci_capacity_scenarios
    assert "dashboard" in TARGETS.ci_capacity_scenarios

    cli = _read("backend/loadtest/run_baseline.py")
    assert "--ci-capacity" in cli
    assert "ci_capacity_scenarios" in cli or "TARGETS.ci_capacity" in cli


def test_load_capacity_mvp_doc():
    doc = _read("docs/LOAD_CAPACITY_MVP.md")
    assert "Stage 26 C1" in doc
    assert "test_load_capacity_c1.py" in doc
    assert "stage26_c1_capacity_evidence.json" in doc
    assert "LOAD_TEST_BASELINE.md" in doc
    assert "1000" in doc
    assert "Remaining" in doc or "deferred" in doc.lower()
    assert "--ci-capacity" in doc or "ci capacity" in doc.lower()

    baseline = _read("docs/LOAD_TEST_BASELINE.md")
    assert "Stage 26 C1" in baseline
    assert "stage26_c1_capacity_evidence.json" in baseline
    assert "test_load_capacity_c1.py" in baseline
    assert "CI capacity" in baseline


def test_load_gate_complete_mvp():
    pr = _read("PRODUCTION_READINESS.md")
    assert "- [x] Load/performance tests meet documented targets." in pr
    assert "- [ ] Load/performance tests meet documented targets." not in pr
    assert "Stage 26 C1" in pr
    assert "test_load_capacity_c1.py" in pr
    assert "stage26_c1_capacity_evidence.json" in pr or "LOAD_CAPACITY_MVP.md" in pr
    assert "1000" in pr
    assert "Remaining" in pr or "operator" in pr.lower()
    # Prior Reliability gates stay Complete
    assert "- [x] Monitoring, metrics, logging and alerting complete." in pr
    assert "- [x] Point-in-time recovery/WAL strategy complete." in pr
    assert "- [x] Kubernetes production deployment reviewed." in pr
