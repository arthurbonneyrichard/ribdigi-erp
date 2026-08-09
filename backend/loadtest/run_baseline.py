#!/usr/bin/env python3
"""CLI: run Stage 5 L1 load-test baseline against a live API.

Examples:
  # Health-only smoke (no credentials)
  python -m loadtest.run_baseline --scenarios health --concurrency 5 --iterations 20

  # Authenticated staging baseline (use a real non-demo tenant account)
  LOADTEST_EMAIL=ops@example.com LOADTEST_PASSWORD='...' LOADTEST_TENANT=acme \\
    python -m loadtest.run_baseline --base-url https://api.example.com \\
      --scenarios health,login,products,dashboard --concurrency 25 --iterations 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from loadtest.config import TARGETS, LoadTestSettings
from loadtest.runner import run_baseline


def main(argv: list[str] | None = None) -> int:
    settings = LoadTestSettings.from_env()
    parser = argparse.ArgumentParser(description="RIBDIGI ERP load-test baseline runner")
    parser.add_argument("--base-url", default=settings.base_url)
    parser.add_argument("--scenarios", default=settings.scenarios)
    parser.add_argument("--concurrency", type=int, default=settings.concurrency)
    parser.add_argument("--iterations", type=int, default=settings.iterations)
    parser.add_argument("--timeout", type=float, default=settings.timeout_seconds)
    parser.add_argument("--email", default=settings.email)
    parser.add_argument("--password", default=settings.password)
    parser.add_argument("--tenant", default=settings.tenant_slug)
    parser.add_argument("--totp", default=settings.totp_code)
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=TARGETS.smoke_max_error_rate,
        help="Fail if any scenario error rate exceeds this (default 0)",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=None,
        help="Optional p95 latency gate in milliseconds",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use CI smoke defaults (health only, small concurrency)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report only")
    args = parser.parse_args(argv)

    scenarios = args.scenarios
    concurrency = args.concurrency
    iterations = args.iterations
    max_p95 = args.max_p95_ms
    if args.smoke:
        scenarios = "health"
        concurrency = TARGETS.smoke_concurrency
        iterations = TARGETS.smoke_iterations
        max_p95 = TARGETS.smoke_p95_ms if max_p95 is None else max_p95

    report = asyncio.run(
        run_baseline(
            base_url=args.base_url,
            scenarios=scenarios,
            concurrency=concurrency,
            iterations=iterations,
            timeout_seconds=args.timeout,
            email=args.email,
            password=args.password,
            tenant_slug=args.tenant,
            totp_code=args.totp,
            max_error_rate=args.max_error_rate,
            max_p95_ms=max_p95,
        )
    )
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("RIBDIGI load-test baseline")
        print(f"  base_url={payload['base_url']} concurrency={payload['concurrency']} iterations={payload['iterations']}")
        print(f"  elapsed_ms={payload['elapsed_ms']} passed={payload['passed']}")
        for name, st in payload["scenarios"].items():
            print(
                f"  - {name}: count={st['count']} errors={st['errors']} "
                f"error_rate={st['error_rate']} p50={st['p50_ms']}ms p95={st['p95_ms']}ms"
            )
        if payload["failures"]:
            print("Failures:")
            for f in payload["failures"]:
                print(f"  ! {f}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
