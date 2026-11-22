# O3: Content-Security-Policy with per-response nonces, rollout runbook

Status: code ready and tested in a real browser (21 Nov 2026). **Not enabled in production.** The default mode changes nothing.

## What changes
Before: `script-src 'self' 'unsafe-inline'`, so any injected inline script would run.
After (enforce mode): `script-src 'self' 'nonce-<fresh value per response>'`. Only scripts the server stamped with that response's nonce run. An attacker who injects a `<script>` into a page cannot guess the nonce, so it is blocked. Styles still allow inline (`style-src 'unsafe-inline'`); that is a separate, lower-risk item.

How it works
- `frontend/proxy.ts` makes a new random nonce for every request and builds the policy from `frontend/lib/csp.ts`.
- Next.js stamps its own scripts with the nonce. `app/layout.tsx` stamps the three small inline scripts (theme, service worker, date picker).
- Every page is now rendered per request (needed for a fresh nonce). Pages are no longer prebuilt static HTML; the app is a signed-in app, so this is fine, but the public storefront/menu/booking pages are a little heavier per view.
- Violation reports go to `/api/csp-report` (one log line each: blocked directive and address, query strings removed).
- `serve.cjs` (the production start command) sets the old enforced header in report-only mode; it must stay the container's start command (the Dockerfile already uses it).

## Modes (`CSP_MODE`, set on the frontend service, read at run time)
| Mode | Enforced | Reported only | Use |
| --- | --- | --- | --- |
| `legacy` (default in production) | old policy, `'unsafe-inline'` | nothing | Today's behaviour. |
| `report-only` | old policy | strict nonce policy + reports | Trial: nothing can break; violations are logged. |
| `enforce` | strict nonce policy | nothing | Final state. |
In development the default is `report-only`.

## What I tested (production build, Chrome, restored copy of development data, 21 Nov 2026)
- Headers per mode are as in the table; the nonce is different on every response; all 16 scripts on the sign-in page carry the nonce.
- **Report-only:** public pages and signed-in screens for retail, restaurant, hotel, bakery, FMCG, gym and HRM: 0 violations.
- **Enforce:** same pass, 0 violations; the theme script ran (so nonce'd inline scripts execute); sign-in (not sign-out), page navigation, POS, restaurant till, reports, accounting, company, security, users, purchasing, hotel tabs, gym tabs loaded.
- **Control check:** an inline script injected without a nonce was blocked and reported, so a clean result is meaningful.
- **Print popups:** a script written into a popup window is blocked under the strict policy. The bakery trade statement and the bakery server print pages used inline scripts to print themselves; both now print from the page (`TradeDesk.tsx`, `lib/bakeryTill.ts`). Other popups already printed from the page.
- Not tested: real printing (headless browser), a payment gateway redirect, Umami analytics enabled, the offline service worker over a long session, Safari/Firefox, mobile browsers.

## Rollout (needs the owner's approval for each step)
1. **Deploy the code with the default.** `CSP_MODE` unset means `legacy`: headers identical to today. Check sign-in and a few pages.
2. **Report-only on production.** In Dokploy set `CSP_MODE=report-only` on the frontend and redeploy. Watch the frontend logs for `"event":"csp_violation"` for several days of real use (all roles: cashier till, kitchen screens, hotel desk, platform console, public booking and shop pages, any printing). Any line is a script the strict policy would block.
3. **Fix what shows up**, repeat step 2 until a full week is quiet.
4. **Enforce.** Set `CSP_MODE=enforce` and restart. Verify sign-in, till sale, printing, an email-link page (reset password), the public shop and booking pages.
5. **Rollback** at any time: set `CSP_MODE=legacy` (or remove it) and restart the frontend. No rebuild, no data involved.

## Known limits
- Browser extensions that inject inline scripts can log violations; they are the user's extension, not the app.
- If analytics is turned on later, its host is added to `script-src` automatically (only when both Umami settings are set).
- `style-src 'unsafe-inline'` stays; moving styles to nonces is a larger change across the app.
