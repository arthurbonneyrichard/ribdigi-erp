# Commercial readiness audit and security check, 20 Nov 2026

Scope: backend (`backend/app`), web app (`frontend`), configuration, dependencies, and the HR work added this week. Method: tool scans, a route-by-route authentication check, targeted code review, and the security-relevant test files. This is **not** an external penetration test and not a line-by-line review of the ~1,560 routes. Section 5 says what it does not prove.

## 1. Results

| Check | Result |
| --- | --- |
| Python dependencies (`pip-audit`, requirements.txt) | No known vulnerabilities |
| Web dependencies (`npm audit --omit=dev`) | 0 vulnerabilities |
| Static scan (`bandit -ll`, `app/`) | 15 findings, all reviewed: none exploitable (see 2) |
| Secrets in the repository | None. Only `.env.example`, `.env.production.example` and test fixtures |
| Unauthenticated routes | 80 of 1,560, each a deliberate public surface (see 3) |
| Production start-up guards | Refuses weak secrets, DEBUG on, rate limiting off, password-only login, mock gateways, mock AI (`config.validate_production_security`) |
| Security-relevant tests (62 files) | **341 passed, 1 skipped** (auth, lockout, sessions, API keys, isolation, backup, webhooks, privacy, till lock, HR) |
| Whole backend suite | **Not run to completion** (1,069 files, many hours). It runs in CI |

## 2. Static scan findings (all reviewed)
- 14 "string-built SQL" notes (`audit.py`, `doc_numbers.py`, `schema_align.py`, `schema_compat.py`, `tenants.py`): identifiers come from database metadata or constants and are quoted; every value is a bound parameter. Not injectable.
- SHA-1 in `restaurant.py`: a change-detection fingerprint, not a security control.

## 3. Unauthenticated routes (all intentional)
Login, 2FA, passkeys, password reset, email verification and unsubscribe; health and readiness; `/metrics` (needs a bearer token in production, otherwise 404); payment webhooks (signature-checked); public menu, restaurant, hotel booking and storefront pages; ZKTeco `/iclock/*` (protocol has no password, documented); gym member portal (private link token header); printer agent pairing; RFID reader punch (own token, SHA-256 stored); legal pages; hotel calendar feed (secret token in the URL).

## 4. Findings
**Fixed in this audit**
1. **GPS blocked on production (functional, medium).** `frontend/next.config.mjs` sent `Permissions-Policy: geolocation=()`, which denies the browser's location prompt to the app itself. HR GPS clock-in, FMCG visit check-in and FMCG quality screens call `navigator.geolocation`, so they would have failed on production builds. Changed to `geolocation=(self)`. Camera/microphone policy unchanged.

**Open, low**
2. `coupons.product_category_ids` looks up products by id without a company check. Reads only a category id, which is then compared inside the caller's own coupon rules; no data returned. Add a `tenant_id` filter when next touched.
3. Password policy is 8 characters with complexity rules. Consider a 12-character minimum for admin and platform roles.
4. CSP still allows `'unsafe-inline'` for scripts (Next.js inline bootstrap). Moving to nonces is the remaining part of O3.

**Carried forward from the 29 Oct audit (not re-reported as new)**
- O2: the JWT secret is reused to derive encryption keys. Needs a dedicated key plus a re-encrypt migration.
- O3: CSP nonces (see 4).
- O9: no external penetration test and no real restore drill on production data.

## 5. What this does not prove
- No penetration test, fuzzing, or load test was run. Cross-company isolation is covered by tests for the modules they target, not proven for every endpoint; the `db.get(...)` review sampled the 98 lookups with no nearby company check and found no exploitable one.
- RFID card attendance and ZKTeco terminals are tested with simulated traffic only. Neither has run on real hardware.
- PAYE, SSNIT and Tier 2 and 3 defaults are starting values. An accountant must check them against current GRA and SSNIT tables before anyone is paid. The system does not file with GRA or SSNIT.
- Live card gateway, GRA E-VAT, hotel OTA connections, key cards and delivery apps are external integrations not covered here.
- The shared working tree held other sessions' uncommitted changes while this ran; tests were run against it as it stood.

## 6. Before selling to customers (checklist)
1. External penetration test (O9) and a restore drill from a production backup.
2. Dedicated encryption key and re-encrypt (O2).
3. Accountant sign-off on payroll rates; first payroll run checked by hand.
4. Run the full CI suite on the commit being promoted, then promote `main` to `production` (never force-push).
5. Real-device test of GPS clock-in after the header fix, and of any RFID or biometric reader that will be sold.
