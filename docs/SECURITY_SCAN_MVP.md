# Security Scan MVP — OWASP Baseline Evidence

**Status:** Complete (MVP) — Stage 27 S1  
**Evidence:** `backend/tests/test_security_scan_s1.py` · `/opt/cursor/artifacts/security/stage27_s1_security_scan.json`  
**Suites:** `test_owasp_smoke.py`, `test_owasp_suite_o1.py`, `test_owasp_suite_t1.py` (pytest `@pytest.mark.security`)

This is the **MVP security scan surface**: durable inventory of automated OWASP baseline controls already exercised in main CI via `pytest -m "security or isolation"`. It is **not** a claim that a vendor penetration test was purchased, or that OWASP ZAP ran green against staging in CI.

## What CI already proves

| Control | Suite evidence |
|---------|----------------|
| A01 Broken Access Control / IDOR | `test_owasp_suite_o1.py`, `test_owasp_suite_t1.py`, isolation matrices |
| A02 Cryptographic Failures (secret leakage, tampered JWT) | `test_owasp_suite_o1.py` |
| A03 Injection / XSS-as-JSON | smoke + o1 + t1 |
| A05 Security Misconfiguration (opaque 404, OpenAPI prod gate, headers) | smoke + o1 + t1 |
| A07 Identification / Authentication Failures | smoke lockout + o1/t1 bearer/API-key |

Main workflow: `.github/workflows/ci.yml` → backend job runs security/isolation markers before the full suite (Stage 18 C1 deploy-free).

## Operator ZAP template (Remaining)

Optional, **not** wired into main `ci.yml` (requires a real staging URL / auth — do not invent green ZAP without a target):

- `ops/security/zap-baseline.example.yml` — copy into a staging-only workflow when ready
- `ops/security/README.md` — operator notes

## Vendor pen-test / ZAP staging pack (Stage 29 V1)

Authoritative pack: [PENTEST_PACK_MVP.md](PENTEST_PACK_MVP.md) · `ops/security/pentest-engagement-checklist.json` · `ops/security/vendor-engagement.example.json`.

Packaging covers engagement checklist + OWASP scope matrix + evidence schema. Evidence keeps `vendor_pen_test_purchased: false`, `live_zap_executed: false`. Purchased vendor certificate and green live ZAP remain **Remaining**.

## Explicitly Remaining

- Vendor / third-party penetration test **purchase / execution** (Stage 29 V1 packs engagement only)
- Live ZAP baseline (or full Top 10) against authenticated staging in CI
- Claiming ZAP HTML/JSON pass artifacts without a real scan run

## Sign-off

Stage 27 S1 is met when this doc + evidence JSON exist, `test_security_scan_s1.py` passes, SECURITY_GUIDE / PRODUCTION_READINESS cite Stage 27 S1 with vendor pen test / live ZAP Remaining, and main `ci.yml` stays deploy-free. Stage 29 V1 is met when `docs/PENTEST_PACK_MVP.md` + checklist + `test_pentest_pack_v1.py` pass without inventing a purchased cert.

See also Stage 210 Tenant MVP Security Scan remaining-gate index fidelity (`docs/SECURITY_SCAN_REMAINING_GATE_MVP.md`, ADR-426 / ADR-427) — packaging non-claim as live security-scan Complete.
