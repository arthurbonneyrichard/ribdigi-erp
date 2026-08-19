# Load Cert Pack MVP — Operator ~1000-VU Certification Packaging

**Status:** Complete (MVP) — Stage 28 C1  
**Evidence:** `backend/tests/test_load_cert_pack_c1.py` · `/opt/cursor/artifacts/loadtest/stage28_c1_load_cert_pack.json`  
**Checklist map:** `ops/loadtest/1000vu-cert-checklist.json`  
**Run schema example:** `ops/loadtest/operator_1000vu_run.example.json`  
**Related:** [LOAD_CAPACITY_MVP.md](LOAD_CAPACITY_MVP.md) (Stage 26 C1) · [LOAD_TEST_BASELINE.md](LOAD_TEST_BASELINE.md) · `backend/loadtest/`

This is the **MVP operator ~1000-VU certificate packaging surface**: a versioned checklist + run-artifact schema extending Stage 26 C1 CI capacity. It is **not** a forged ~1000-VU Locust/httpx certificate and does **not** claim a live staging capacity run already passed.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Execute on sized staging with a real tenant; fill run JSON; log in ops change log |
| `ci_proven` | Smoke + CI capacity profiles (Stage 26 C1) + this pack honesty |
| `deferred` | Certified 1000-VU in CI; forged `passed: true` without a real run; ZAP-under-load |

## Targets (operator)

| Metric | Target |
|--------|--------|
| Concurrent users | ~1000 |
| p95 latency | &lt; 500 ms |
| Error rate | 0% |

CI capacity remains ASGI-honest at modest concurrency (`--ci-capacity`) — see Stage 26 C1.

## Automation hooks

1. Maintain `ops/loadtest/1000vu-cert-checklist.json` as the authoritative step map (synced by `test_load_cert_pack_c1.py`).
2. Operators copy `operator_1000vu_run.example.json` and fill measured results after a real run.
3. CI proves packaging honesty only: `operator_1000vu_executed: false`, `ci_1000vu_certificate_claimed: false`.

## Explicitly not claimed

- Green CI ~1000-VU / p95 &lt; 500 ms certificate
- Committing a filled `passed: true` run JSON without a real staging run
- Treating Stage 26 C1 / Stage 28 C1 Complete as “1000-VU certified in production”
- Vendor ZAP-under-load Complete

## Sign-off

Stage 28 C1 is met when this doc + checklist + run schema example + evidence JSON exist, `test_load_cert_pack_c1.py` passes, and PRODUCTION_READINESS / launch / roadmap cite Stage 28 C1 without inventing a live 1000-VU certificate.

See also Stage 223 load cert pack remaining-gate index: [`LOAD_CERT_PACK_REMAINING_GATE_MVP.md`](LOAD_CERT_PACK_REMAINING_GATE_MVP.md).
