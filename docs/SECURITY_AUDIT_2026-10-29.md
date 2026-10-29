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
