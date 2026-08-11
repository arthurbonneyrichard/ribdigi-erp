"""Load-test baseline configuration (env-overridable)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineTargets:
    """Documented MVP targets. Staging full runs aim higher than CI smoke."""

    # Roadmap aspirational (staging / capacity run)
    staging_concurrent_users: int = 1000
    staging_transactions_per_second: int = 100
    staging_p95_ms: float = 500.0
    staging_max_error_rate: float = 0.0

    # CI / local harness smoke (proves scripts work; not a capacity claim)
    smoke_concurrency: int = 5
    smoke_iterations: int = 20
    smoke_p95_ms: float = 2000.0
    smoke_max_error_rate: float = 0.0

    # Stage 26 C1 — CI capacity profile (ASGI / modest concurrency; not 1000-VU)
    ci_capacity_concurrency: int = 10
    ci_capacity_iterations: int = 20
    ci_capacity_p95_ms: float = 500.0
    ci_capacity_max_error_rate: float = 0.0
    ci_capacity_scenarios: str = "health,login,products,dashboard"


@dataclass
class LoadTestSettings:
    base_url: str = "http://localhost:8000"
    tenant_slug: str = ""
    email: str = ""
    password: str = ""
    totp_code: str = ""
    concurrency: int = 10
    iterations: int = 50
    timeout_seconds: float = 30.0
    scenarios: str = "health,login,products,dashboard"

    @classmethod
    def from_env(cls) -> "LoadTestSettings":
        return cls(
            base_url=os.getenv("LOADTEST_BASE_URL", "http://localhost:8000").rstrip("/"),
            tenant_slug=os.getenv("LOADTEST_TENANT", ""),
            email=os.getenv("LOADTEST_EMAIL", ""),
            password=os.getenv("LOADTEST_PASSWORD", ""),
            totp_code=os.getenv("LOADTEST_TOTP", ""),
            concurrency=int(os.getenv("LOADTEST_CONCURRENCY", "10")),
            iterations=int(os.getenv("LOADTEST_ITERATIONS", "50")),
            timeout_seconds=float(os.getenv("LOADTEST_TIMEOUT", "30")),
            scenarios=os.getenv(
                "LOADTEST_SCENARIOS", "health,login,products,dashboard"
            ),
        )


TARGETS = BaselineTargets()
