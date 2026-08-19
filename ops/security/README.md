# Security scan operator notes (Stage 27 S1 + Stage 29 V1)

MVP automated OWASP baseline evidence is proven in main CI via pytest `security` / `isolation` markers — see `docs/SECURITY_SCAN_MVP.md` and `backend/tests/test_security_scan_s1.py`.

| File | Role |
|------|------|
| `zap-baseline.example.yml` | Optional GitHub Actions ZAP baseline template — **not** wired into `.github/workflows/ci.yml` |
| `pentest-engagement-checklist.json` | Stage 29 V1 engagement steps + scope matrix |
| `vendor-engagement.example.json` | Stage 29 V1 engagement report schema (`passed: false` placeholder) |

## Why ZAP is not in main CI

Stage 18 C1 keeps main CI deploy-free. A ZAP job needs a reachable staging base URL and auth cookies/headers. Wiring ZAP without a real target invents a green scan. Copy the example into a **staging-only** workflow when operators provide those secrets.

## Remaining

- Vendor penetration test **purchase / execution** (Stage 29 V1 packaging Complete MVP — `docs/PENTEST_PACK_MVP.md`)
- Live ZAP against staging (authenticated) with retained HTML/JSON reports

Authoritative V1 pack: `docs/PENTEST_PACK_MVP.md` (`test_pentest_pack_v1.py`).
