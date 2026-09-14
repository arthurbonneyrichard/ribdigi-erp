"""Stage 18 C1: CI workflow + production Compose/env template fidelity."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.rate_limit import rate_limiter

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
ENV_PROD = ROOT / ".env.production.example"
ENV_DEV = ROOT / ".env.example"
COMPOSE_PROD = ROOT / "docker-compose.prod.yml"
COMPOSE_DEV = ROOT / "docker-compose.yml"
PYTEST_INI = ROOT / "backend" / "pytest.ini"


def test_ci_runs_pytest_markers_and_frontend_build_no_k8s():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "pytest" in text
    assert (
        '-m "security or isolation or store_scope"' in text
        or "-m 'security or isolation or store_scope'" in text
        or '-m "security or isolation"' in text
        or "-m 'security or isolation'" in text
    )
    assert "store_scope" in text
    assert "npm run build" in text
    assert "setup-python" in text
    assert "setup-node" in text
    assert "test_store_scope_rbac_matrix.py" in text
    lowered = text.lower()
    assert "kubernetes" not in lowered or "no kubernetes" in lowered
    assert "helm" not in lowered or "no " in lowered
    assert "kubectl" not in lowered
    # No deploy job names
    assert "deploy:" not in text
    assert "jobs:" in text
    assert "backend:" in text
    assert "frontend:" in text


def test_pytest_ini_declares_security_and_isolation_markers():
    text = PYTEST_INI.read_text(encoding="utf-8")
    assert "security:" in text
    assert "isolation:" in text
    assert "store_scope:" in text


def test_production_env_template_aligned_with_s1_validators():
    text = ENV_PROD.read_text(encoding="utf-8")
    assert "APP_ENV=production" in text
    assert "DEBUG=false" in text
    assert "RATE_LIMIT_ENABLED=true" in text
    assert "RATE_LIMIT_BACKEND=redis" in text
    assert "RATE_LIMIT_REQUIRE_REDIS=true" in text
    assert "CORS_ORIGINS=" in text
    assert "*" not in [
        part.strip()
        for line in text.splitlines()
        if line.startswith("CORS_ORIGINS=")
        for part in line.split("=", 1)[1].split(",")
    ]
    assert "JWT_SECRET_KEY=" in text
    assert "REQUEST_LOG_ENABLED=true" in text
    assert "METRICS_ENABLED=true" in text
    assert "METRICS_REQUIRE_AUTH=true" in text
    assert "METRICS_BEARER_TOKEN=" in text
    assert "TRUST_X_FORWARDED_FOR=" in text
    assert "ALLOW_DEVELOPMENT_SEED=false" in text
    assert "TOTP_ENCRYPTION_KEY=" in text
    assert "BACKUP_ENCRYPTION_KEY=" in text
    assert "ALLOW_PUBLIC_TENANT_SIGNUP=false" in text

    # Template values must satisfy Settings production validator
    from cryptography.fernet import Fernet

    cfg = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="x" * 32,
        DEBUG=False,
        CORS_ORIGINS="https://app.example.com",
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_BACKEND="redis",
        RATE_LIMIT_REQUIRE_REDIS=True,
        EMAIL_ENABLED=False,
        SMS_ENABLED=False,
        ALLOW_DEVELOPMENT_SEED=False,
        ALLOW_PUBLIC_TENANT_SIGNUP=False,
        METRICS_ENABLED=True,
        METRICS_REQUIRE_AUTH=True,
        METRICS_BEARER_TOKEN="x" * 16,
        REQUEST_LOG_ENABLED=True,
        TOTP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        BACKUP_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    )
    assert cfg.RATE_LIMIT_REQUIRE_REDIS is True
    assert cfg.APP_ENV == "production"
    assert cfg.METRICS_REQUIRE_AUTH is True
    assert cfg.ALLOW_PUBLIC_TENANT_SIGNUP is False


def test_production_compose_overlay_no_reload_requires_redis_rate_limit():
    text = COMPOSE_PROD.read_text(encoding="utf-8")
    assert "env_file: .env.production" in text
    assert "RATE_LIMIT_REQUIRE_REDIS" in text
    assert "RATE_LIMIT_BACKEND: redis" in text
    assert "APP_ENV: production" in text
    assert "--workers" in text
    assert "uvicorn app.main:app" in text
    # Ensure command does not pass reload flag to uvicorn
    command_blob = text.split("command:")[-1]
    assert "--reload" not in command_blob
    # No deploy manifests — comments may mention deferred K8s/Helm explicitly
    assert "kind: Deployment" not in text
    assert "apiVersion:" not in text
    assert "helm upgrade" not in text.lower()
    assert "kubectl " not in text.lower()
    # Dev compose still exists for local work
    assert COMPOSE_DEV.is_file()


def test_dev_env_example_points_at_production_template():
    text = ENV_DEV.read_text(encoding="utf-8")
    assert "RATE_LIMIT_ENABLED=true" in text
    assert ".env.production.example" in text
    assert "docker-compose.prod.yml" in text


def test_production_rejects_require_redis_with_memory_backend():
    with pytest.raises(Exception) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_BACKEND="memory",
            RATE_LIMIT_REQUIRE_REDIS=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
    assert "RATE_LIMIT_REQUIRE_REDIS" in str(exc.value)


def test_production_rejects_wildcard_cors_and_weak_jwt():
    with pytest.raises(Exception) as exc_cors:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="x" * 32,
            DEBUG=False,
            CORS_ORIGINS="*",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
    assert "CORS" in str(exc_cors.value) or "wildcard" in str(exc_cors.value).lower()

    with pytest.raises(Exception) as exc_jwt:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="change-me",
            DEBUG=False,
            CORS_ORIGINS="https://app.example.com",
            RATE_LIMIT_ENABLED=True,
            EMAIL_ENABLED=False,
            SMS_ENABLED=False,
        )
    assert "JWT" in str(exc_jwt.value)


def test_health_omits_security_posture_under_c1():
    """SEC-L2 — C1 prod-config hardening must not reintroduce public posture."""
    rate_limiter.reset_for_tests()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "security" not in data
    assert "env" not in data
    assert data["status"] == "ok"
