# Load Capacity MVP (Stage 26 C1)

**Status:** Documented — Stage 26 C1 CI capacity evidence  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Related:** Stage 5 L1 (`test_loadtest_baseline_l1.py`), Stage 18 T1 (`test_loadtest_evidence_t1.py`), Stage 26 C1 (`test_load_capacity_c1.py`)  
**Evidence:** `/opt/cursor/artifacts/loadtest/stage26_c1_capacity_evidence.json`  
**Targets:** [LOAD_TEST_BASELINE.md](LOAD_TEST_BASELINE.md)

This is the **MVP load capacity surface**: httpx harness + CI smoke + CI capacity profiles with durable artifacts. It is **not** a claim that a ~1000-VU staging Locust/httpx run has been certified in CI.

## Profiles

| Profile | Concurrency | Iterations | Scenarios | p95 gate | Where |
|---------|-------------|------------|-----------|----------|-------|
| Smoke | 5 | 20 | `health` | < 2000 ms | CI / ASGI / live |
| CI capacity (Stage 26 C1) | 10 | 20 | `health,login,products,dashboard` | < 500 ms | CI / ASGI |
| Staging capacity (operator) | up to 1000 | operator | same + Locust optional | < 500 ms | Sized staging |

## Harness

```bash
cd backend
python -m loadtest.run_baseline --smoke \
  --output /opt/cursor/artifacts/loadtest/stage18_t1_baseline_smoke.json

# Stage 26 C1 profile (needs LOADTEST_* creds against a live API)
python -m loadtest.run_baseline --ci-capacity \
  --email "$LOADTEST_EMAIL" --password "$LOADTEST_PASSWORD" \
  --tenant "$LOADTEST_TENANT" --totp "$LOADTEST_TOTP" \
  --output /opt/cursor/artifacts/loadtest/stage26_c1_capacity_cli.json
```

Automated CI proof writes `stage26_c1_capacity_evidence.json` via `test_load_capacity_c1.py` (ASGI transport — no invented 1000-VU certificate).

## Operator staging 1000-VU checklist (Remaining)

1. Size staging API + DB + Redis/Rabbit; tune `RATE_LIMIT_*` so the run measures capacity, not intentional 429s.
2. Use a real staging tenant (never demo/production secrets in git).
3. Run Locust or httpx toward ~1000 concurrent users; record p95 < 500 ms and 0% errors.
4. Scrape `/api/v1/metrics` during the run (`ribdigi_http_requests_total`).
5. Attach the report to the launch change log.

Optional Locust: `backend/loadtest/locustfile.py` (see `LOAD_TEST_BASELINE.md`).

## Explicitly deferred

- Certified ~1000-VU staging capacity certificate in CI
- PgBouncer / Redis app-cache capacity labs
- Vendor ZAP-in-CI Top 10 under load

## Sign-off

Stage 26 C1 is met when smoke + CI capacity profiles pass, the evidence artifact exists, and PRODUCTION_READINESS load gate is Complete (MVP) with Remaining limited to operator staging ~1000-VU.
