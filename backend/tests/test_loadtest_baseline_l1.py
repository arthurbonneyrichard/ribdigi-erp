"""Stage 5 L1: load-test baseline harness smoke against ASGI app."""

from __future__ import annotations

import pyotp
import pytest
from httpx import ASGITransport

from app.main import app
from loadtest.config import TARGETS
from loadtest.runner import run_baseline
from loadtest.scenarios import resolve_scenarios


def test_resolve_scenarios_and_targets():
    names = [s.name for s in resolve_scenarios("health,login,products,dashboard")]
    assert names == ["health", "login", "products", "dashboard"]
    with pytest.raises(ValueError, match="Unknown"):
        resolve_scenarios("not-a-scenario")
    assert TARGETS.staging_concurrent_users == 1000
    assert TARGETS.smoke_concurrency >= 1


@pytest.mark.asyncio
async def test_baseline_health_smoke_asgi(client):
    _ac, _seed = client
    report = await run_baseline(
        base_url="http://test",
        scenarios="health",
        concurrency=TARGETS.smoke_concurrency,
        iterations=TARGETS.smoke_iterations,
        transport=ASGITransport(app=app),
        max_error_rate=TARGETS.smoke_max_error_rate,
        max_p95_ms=TARGETS.smoke_p95_ms,
    )
    assert report.passed, report.failures
    assert report.scenarios["health"].count == TARGETS.smoke_iterations
    assert report.scenarios["health"].error_rate == 0.0


@pytest.mark.asyncio
async def test_baseline_authenticated_scenarios_asgi(client, db_session):
    _ac, seed = client
    # Avoid concurrent first-hit catalog seed races under SQLite (UNIQUE code).
    from app import catalog_meta as catalog_meta_svc

    await catalog_meta_svc.ensure_default_catalog(db_session, seed["t1"].id)
    await db_session.commit()

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    report = await run_baseline(
        base_url="http://test",
        scenarios="login,products,dashboard",
        concurrency=3,
        iterations=5,
        transport=ASGITransport(app=app),
        email="super@alpha.example.com",
        password="SecurePass123!",
        tenant_slug="alpha",
        totp_code=code,
        max_error_rate=0.0,
        max_p95_ms=TARGETS.smoke_p95_ms,
    )
    assert report.passed, report.to_dict()
    for name in ("login", "products", "dashboard"):
        assert name in report.scenarios
        assert report.scenarios[name].errors == 0
