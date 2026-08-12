# Load Test Baseline (Stage 5 L1)

**Scope:** Runnable baseline scripts + documented targets for RIBDIGI BUSINESS ERP API  
**Out of scope this pass:** Claiming a production 1000-VU capacity certificate in CI; Redis app-data cache / PgBouncer (parked after L1)

## Targets

| Tier | Concurrent users | Throughput guide | p95 latency | Error rate |
|------|------------------|------------------|-------------|------------|
| **CI / harness smoke** | 5 | ~health-only | < 2000 ms | 0% |
| **CI capacity** (Stage 26 C1) | 10 | health + auth scenarios | < 3000 ms (ASGI) | 0% |
| **Staging capacity** (operator) | up to 1000 | ~100 TPS aspirational | < 500 ms | 0% |
| **Product aspirational** (roadmap) | 1000 | 100 TPS | API < 200 ms (prod opt) | 0% |

CI proves the harness works. Staging Locust/httpx runs produce the capacity evidence for launch sign-off.

## Scenarios

| Name | Endpoint(s) | Auth |
|------|-------------|------|
| `health` | `GET /api/v1/health` | No |
| `health_ready` | `GET /api/v1/health/ready` | No |
| `login` | `POST /api/v1/auth/login` | Credentials |
| `products` | login + `GET /api/v1/products` | Yes |
| `dashboard` | login + `GET /api/v1/dashboard` | Yes |

Roadmap also calls out invoice creation under load — extend `loadtest/scenarios.py` when a stable non-destructive create path is available for capacity labs.

## Credentials

Use a **real staging tenant** account via environment variables. Do not commit passwords or seed demo tenants into production.

```bash
export LOADTEST_BASE_URL=https://api.staging.example.com
export LOADTEST_TENANT=your-tenant-slug
export LOADTEST_EMAIL=ops@example.com
export LOADTEST_PASSWORD='…'
export LOADTEST_TOTP=123456   # if role requires MFA
```

## httpx baseline runner

From `backend/`:

```bash
# CI-style smoke (health only)
python -m loadtest.run_baseline --smoke

# Authenticated local/staging
python -m loadtest.run_baseline \
  --scenarios health,login,products,dashboard \
  --concurrency 25 --iterations 100 \
  --max-p95-ms 500 --max-error-rate 0
```

Exit code `0` = thresholds met; JSON via `--json`.

## Locust (optional staging)

```bash
pip install locust
cd backend
locust -f loadtest/locustfile.py --host "$LOADTEST_BASE_URL" \
  --users 100 --spawn-rate 10 --run-time 5m --headless
```

Scale toward 1000 users only on sized staging infra with rate limits tuned (`RATE_LIMIT_*`) so the test measures app capacity, not intentional 429s.

## Automated proof

`backend/tests/test_loadtest_baseline_l1.py` runs the harness against the ASGI test app (health + authenticated products/dashboard) and asserts zero errors under smoke concurrency.

### Stage 18 T1 — evidence artifact path

CI / agent runs write a JSON evidence file for launch fidelity:

| Path | Contents |
|------|----------|
| `/opt/cursor/artifacts/loadtest/stage18_t1_baseline_smoke.json` | Smoke baseline report (`passed`, scenario stats, p50/p95) |

Also supported by the CLI:

```bash
python -m loadtest.run_baseline --smoke --output /opt/cursor/artifacts/loadtest/stage18_t1_baseline_smoke.json
```

Automated proof: `backend/tests/test_loadtest_baseline_l1.py` + `test_load_capacity_c1.py`. This is **harness evidence**, not a certified 1000-VU capacity certificate (still deferred).

### Stage 26 C1 — CI capacity evidence

| Path | Contents |
|------|----------|
| `/opt/cursor/artifacts/loadtest/stage26_c1_capacity_evidence.json` | Smoke + CI capacity profiles (`passed`, scenario stats, `operator_1000vu_required`) |

```bash
python -m loadtest.run_baseline --ci-capacity \
  --email "$LOADTEST_EMAIL" --password "$LOADTEST_PASSWORD" \
  --tenant "$LOADTEST_TENANT" \
  --output /opt/cursor/artifacts/loadtest/stage26_c1_capacity_cli.json
```

Automated proof: `backend/tests/test_load_capacity_c1.py`. Authoritative MVP doc: `docs/LOAD_CAPACITY_MVP.md`. Stage 28 C1 packages the operator ~1000-VU checklist/schema (`docs/LOAD_CERT_PACK_MVP.md`, `ops/loadtest/`, `test_load_cert_pack_c1.py`) — live staging ~1000-VU **execution** remains Remaining.

## Sign-off checklist (staging)

1. [ ] Rate limits documented for the run (or temporarily raised on staging).
2. [ ] `--scenarios health,login,products,dashboard` (or Locust) completed.
3. [ ] p95 < 500 ms and 0% errors recorded in change log / PR note.
4. [ ] `/metrics` scraped during the run for request counters (Stage 5 H5).
