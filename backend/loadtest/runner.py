"""Async concurrent load-test runner with p50/p95 and error-rate stats."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from loadtest.scenarios import Scenario, resolve_scenarios


@dataclass
class Sample:
    scenario: str
    ok: bool
    latency_ms: float
    error: str | None = None
    status_code: int | None = None


@dataclass
class ScenarioStats:
    name: str
    samples: list[Sample] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def errors(self) -> int:
        return sum(1 for s in self.samples if not s.ok)

    @property
    def error_rate(self) -> float:
        return (self.errors / self.count) if self.count else 0.0

    def percentile(self, p: float) -> float:
        ok_lat = sorted(s.latency_ms for s in self.samples if s.ok)
        if not ok_lat:
            return float("inf")
        if len(ok_lat) == 1:
            return ok_lat[0]
        k = (len(ok_lat) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ok_lat[int(k)]
        return ok_lat[f] * (c - k) + ok_lat[c] * (k - f)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "p50_ms": round(self.percentile(50), 2) if self.count else None,
            "p95_ms": round(self.percentile(95), 2) if self.count else None,
            "max_ms": round(max((s.latency_ms for s in self.samples), default=0), 2),
        }


@dataclass
class RunReport:
    base_url: str
    concurrency: int
    iterations: int
    elapsed_ms: float
    scenarios: dict[str, ScenarioStats]
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "concurrency": self.concurrency,
            "iterations": self.iterations,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "passed": self.passed,
            "failures": self.failures,
            "scenarios": {k: v.summary() for k, v in self.scenarios.items()},
        }


async def _one(
    client: httpx.AsyncClient,
    scenario: Scenario,
    ctx_template: dict[str, Any],
) -> Sample:
    ctx = dict(ctx_template)
    # Per-iteration auth cache: login once per worker context copy is fine;
    # products/dashboard will login if needed.
    start = time.perf_counter()
    try:
        assert scenario.run is not None
        await scenario.run(client, ctx)
        return Sample(
            scenario=scenario.name,
            ok=True,
            latency_ms=(time.perf_counter() - start) * 1000.0,
        )
    except Exception as exc:
        status = None
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
        return Sample(
            scenario=scenario.name,
            ok=False,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            error=str(exc)[:300],
            status_code=status,
        )


async def run_baseline(
    *,
    base_url: str,
    scenarios: str | list[str],
    concurrency: int = 5,
    iterations: int = 20,
    timeout_seconds: float = 30.0,
    email: str = "",
    password: str = "",
    tenant_slug: str = "",
    totp_code: str = "",
    transport: httpx.AsyncBaseTransport | None = None,
    max_error_rate: float = 0.0,
    max_p95_ms: float | None = None,
) -> RunReport:
    """Run scenarios with a fixed worker pool until `iterations` complete per scenario."""
    resolved = resolve_scenarios(scenarios)
    stats = {s.name: ScenarioStats(name=s.name) for s in resolved}
    ctx_template = {
        "email": email,
        "password": password,
        "tenant_slug": tenant_slug,
        "totp_code": totp_code,
    }

    # Skip auth scenarios when credentials are missing (health-only smoke).
    runnable = []
    for s in resolved:
        if s.requires_auth and not (email and password and tenant_slug):
            continue
        runnable.append(s)
    if not runnable:
        raise ValueError("No runnable scenarios (auth credentials required?)")

    queue: asyncio.Queue[Scenario | None] = asyncio.Queue()
    for s in runnable:
        for _ in range(iterations):
            await queue.put(s)
    for _ in range(concurrency):
        await queue.put(None)

    started = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=timeout_seconds,
        transport=transport,
        follow_redirects=True,
    ) as client:

        async def worker() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is None:
                        return
                    sample = await _one(client, item, ctx_template)
                    stats[item.name].samples.append(sample)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    failures: list[str] = []
    for name, st in stats.items():
        if st.count == 0:
            continue
        if st.error_rate > max_error_rate:
            failures.append(
                f"{name}: error_rate {st.error_rate:.4f} > {max_error_rate:.4f}"
            )
        if max_p95_ms is not None and st.percentile(95) > max_p95_ms:
            failures.append(
                f"{name}: p95 {st.percentile(95):.1f}ms > {max_p95_ms:.1f}ms"
            )

    return RunReport(
        base_url=base_url,
        concurrency=concurrency,
        iterations=iterations,
        elapsed_ms=elapsed_ms,
        scenarios={k: v for k, v in stats.items() if v.count},
        passed=not failures,
        failures=failures,
    )
