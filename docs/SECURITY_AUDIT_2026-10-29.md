# Ribdigi ERP security audit — 29 October 2026

Scope: backend (FastAPI, 851 routes), frontend (Next.js), dependencies, and the live site https://erp.ribdigihouse.com.
Method: dependency scans (pip-audit, npm audit), static analysis (bandit), a route-by-route auth inventory, targeted code review
(auth, tenancy, uploads, outbound HTTP, SQL, HTML output, secrets), and non-intrusive live checks.
**This is an internal review, not a certification or a penetration test.**

## Fixed in this audit

| ID | Severity | Finding | Fix |
| --- | --- | --- | --- |
| F1 | Critical | Next.js 14.2.35 image optimizer (`/_next/image`) was reachable on the live site. Several advisories give unauthenticated remote code execution or denial of service through it. The app never uses `next/image`. | `images.unoptimized: true` and the middleware returns 404 for `/_next/image`. |
| F2 | High | SSRF: tenant-supplied webhook, bank-feed and WooCommerce URLs could target `http://localhost`, `127.0.0.1` or `host.docker.internal` in production. Hostnames were checked only by name, so a public name pointing at a private address passed. | `http://` local hosts are refused in production. The new `app/outbound.py` resolves the host at send time and refuses loopback, private, link-local and reserved addresses. Test: `test_outbound_guard_production.py`. |
| F3 | High | Pillow 11.0.0 (68 advisories, including an out-of-bounds write on crafted images). It parses user uploads: logos, product images and receipts. | Pillow 13.0.0 |
| F4 | High | pypdf 5.1.0 (96 advisories; crafted PDFs exhaust memory). It parses OCR uploads. | pypdf 6.21.4 |
| F5 | Medium | Starlette 0.47.3 (Range-header denial of service and others). | FastAPI 0.162.0 with Starlette 1.10.0 |
| F6 | Medium | python-multipart 0.0.20 (multipart parsing denial of service on upload endpoints). | 0.0.32 |

## Open — needs a decision or larger work

| ID | Severity | Finding | Recommendation |
| --- | --- | --- | --- |
| O1 | High | Next.js 14.2.35 still has advisories outside the image optimizer: server-component and server-action denial of service, request smuggling in rewrites (the `/api/v1` proxy), and cache poisoning. Every fix needs Next 16.4.3 (a major upgrade, React 19). | Plan the Next 16 upgrade as its own tested release. |
| O2 | Medium | Key reuse: the JWT signing secret always derives the encryption keys for billing and online-shop secrets. It also derives the keys for backups, 2FA, SMTP, SMS and bank credentials when `BACKUP_ENCRYPTION_KEY` / `TOTP_ENCRYPTION_KEY` are unset. One leaked secret then exposes both sessions and stored secrets, and rotating it breaks decryption. | Confirm both keys are set in production. Add a dedicated key for billing and shop secrets, with a re-encryption migration. |
| O3 | Medium | The web app sends no Content-Security-Policy (the API does). Tokens are kept in memory and encrypted IndexedDB, but injected script could still read them. | Add a CSP, starting with `Content-Security-Policy-Report-Only`. |
| O4 | Medium | Rate limits key on the rightmost `X-Forwarded-For` hop. Behind Traefik and the Next.js proxy, every visitor may share one bucket unless `TRUSTED_PROXY_IPS` lists both proxies. Spoofing `X-Forwarded-For` was checked live and does not create new buckets. | Set `TRUSTED_PROXY_IPS` on the server, then check that two networks get separate limits. |
| O5 | Low | python-jose 3.5.0 is unmaintained and has an advisory about key confusion. It is not exploitable here because HS256 is pinned. ecdsa (pulled in by python-jose) has a timing advisory but is unused. | Move to PyJWT. |
| O6 | Low | A rotated refresh token that is reused is rejected, but the rest of the session family is not revoked. | Revoke all of the user's sessions on refresh-token reuse. |
| O7 | Low | The outbound guard resolves the host before httpx connects, so a fast DNS rebind remains possible. | Pin the resolved IP in the transport. |
| O8 | Low | The `Server: uvicorn` header is disclosed. `@app.on_event("startup")` is deprecated in FastAPI 0.162. | Strip the header at the proxy; move to a lifespan handler. |
| O9 | Owner | No external penetration test or production restore drill. | Arrange both before claiming certification. |

## Fixed in the follow-up pass

| ID | Was | Fix |
| --- | --- | --- |
| O3 (part) | No CSP on the web app | Enforced `object-src 'none'; base-uri 'self'`. The full policy runs as `Content-Security-Policy-Report-Only` until each page is checked; then switch it to enforcing. |
| O4 | Recorded IPs could be spoofed, and rate-limit buckets may have been shared | Uvicorn trusts any `X-Forwarded-For`, so `request.client.host` was caller-controlled. Sign-in, session and audit IPs now use `client_ip_from_request`. Without `TRUSTED_PROXY_IPS`, it skips private proxy hops and uses the nearest public address. Test: `test_client_ip_behind_proxies.py`. |
| O5 | python-jose 3.5.0 (unmaintained, advisory) | Replaced with PyJWT 2.15.1; `cryptography` pinned directly. HS256 is still pinned. |
| O6 | Refresh-token reuse not detected | An already-rotated refresh token reused more than 60 s later revokes every session of that user and writes `refresh_token_reuse` to the audit log. Within 60 s (two tabs refreshing at once) it is only refused. Test: `test_refresh_token_reuse.py`. |
| O8 | `Server: uvicorn` header; deprecated `on_event` | `--no-server-header` added to the Dockerfile and both compose files; startup moved to a lifespan handler. |
| O2 (part) | Encryption keys derived from the JWT secret | Production now logs a warning at startup unless `BACKUP_ENCRYPTION_KEY` and `TOTP_ENCRYPTION_KEY` are both set. A dedicated billing/shop key still needs a re-encryption migration. |

Still open: O1 (Next 16 upgrade), O2 (dedicated key and migration), O3 (enforce the full CSP), O7 (pin the resolved IP), O9 (external pentest, production restore drill).

## Verified in place

- **Auth.** JWT algorithm pinned; 15-minute access tokens; refresh tokens rotated and stored hashed; bcrypt passwords; 30-minute lockout after repeated failed logins.
- **2FA.** Production refuses to start without 2FA required (TOTP or passkey).
- **Production startup guard.** The server refuses to start without a strong JWT secret, with `DEBUG` on, with wildcard CORS, without trusted hosts, or with rate limits off.
- **Tenancy.** The tenant always comes from the token or API key, and `X-Tenant-ID` must match (403 otherwise). 65 cross-tenant tests in the suite.
- **Public routes.** 40 of 851 routes need no sign-in: login, password reset, email verification, passkey login, the online shop, public booking, signed payment webhooks, printer-agent pairing, health and the token-gated metrics. All are intended. Pairing uses a 32-bit, 15-minute, single-use code.
- **Webhooks.** Payment webhooks are verified with HMAC and `compare_digest`; outbound webhooks are signed.
- **Uploads.** Size limits apply; SVG/XML uploads are rejected by content sniffing.
- **SQL.** 14 bandit "SQL string" flags reviewed: identifiers come from the database catalog or a strict regex, and values are bound parameters.
- **HTML output.** Print, receipt and email HTML escapes user data.
- **Live site.**
  - HTTPS redirect, HSTS, and TLS 1.0/1.1 refused.
  - nosniff, Referrer-Policy and Permissions-Policy headers present.
  - Frames blocked outside the shop and booking pages.
  - The API serves a strict CSP; its docs and OpenAPI return 404; metrics return 404 without the token.
- **Audit log.** The record chain is serialised per company and verifies (see the 29 Oct readiness entry).
