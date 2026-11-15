# Privacy, legal, security and accessibility audit — 15 November 2026

Scope: the RIBDIGI ERP application (erp.ribdigihouse.com) and its public pages (sign-in, legal pages,
unsubscribe, company shop / booking / menu pages), backend API and emails. **Out of scope:** the Ribdigi House
corporate website (ribdigihouse.com) and any separate ERP marketing site. They are not in this repository and
were not audited.

This is an engineering audit. Creating policy pages does not make the business legally compliant. Every item
under "Needs the owner or a lawyer" below should be reviewed by a qualified Ghanaian lawyer or data protection
professional before relying on it.

Status key: **PASS** implemented and verified · **PARTIAL** implemented, more work needed · **FAIL** not done
or failed · **N/A** not relevant, with the reason.

## 1. What existed before this work

- Privacy Policy and Terms of Service pages (short, accurate, dated 22 Oct 2026), linked from sign-in screens.
- No refund policy, no cookie policy, no cookie settings.
- The ERP sets **no cookies**. Browser local storage holds only functional items (sign-in, theme, menus, till
  offline queue, shop cart, kiosk/lock state).
- Analytics (Umami) was built in with a default address whose server no longer exists; switched off on
  15 Nov (commit fdfa402400) before this audit.
- Every page loaded the font from Google Fonts, sending each visitor's IP address to Google.
- Subscription billing already records renewal consent (version, time, user, plan, amount, VAT), shows the
  price with currency, period and VAT, starts with an unticked agreement box, and has a one-click "turn off
  renewal". The 14-day trial is strict: never charged, never turns paid on its own.
- Hotel guest marketing consent exists and defaults to off.
- Owner Email center sent news to company admins with no unsubscribe link or opt-out.
- No self-service deletion request; staff users can be deleted by a company admin; companies by the owner.
- No public self-sign-up form (companies are created by the owner), no newsletter form, no contact form in the
  app (support is through the signed-in Help & Support desk).

## 2. What was built

| Area | Change |
|---|---|
| Legal pages | Privacy Policy rewritten (controller/processor roles under Act 843, data categories and purposes, legal grounds, processors, payments, international transfers, retention, rights, deletion route, email, children, security, changes). Terms rewritten (eligibility, acceptable use, plans, trial, renewal, payment, cancellation, payments the company takes, ownership, export, availability, suspension, liability, disputes, changes). New **Refund Policy** and **Cookie Policy**. |
| Links | Terms · Privacy · Refunds · Cookies · Cookie settings on every sign-in screen, every legal page and at the foot of the signed-in work area (not on till/kiosk screens). Terms and Refund links beside the renewal agreement box on Company → Billing. |
| Cookie consent | `lib/consent.ts` stores the choice with a version and time; `components/CookieConsent.tsx` banner (Accept all / Reject non-essential / Customize, identical styling) and an accessible settings dialog (focus trap, Escape, focus return). The banner shows only when an optional category actually exists (analytics configured), so no one is asked to "consent" to nothing. Analytics now loads **only after a yes** (`components/UmamiScript.tsx`) and is removed when consent is withdrawn. |
| Font | Plus Jakarta Sans self-hosted from `public/fonts` (SIL OFL 1.1, licence file included); Google Fonts origins removed from the CSP. |
| Unsubscribe | Owner Email center sends are now **marketing** (default) or **service notice**. Marketing skips unsubscribed addresses, carries a personal unsubscribe link in text and HTML, and RFC 8058 one-click headers (`List-Unsubscribe`, `List-Unsubscribe-Post`). Links are HMAC-signed per address, need no sign-in, and cannot be used for another address. Public page `/unsubscribe`; API `GET|POST /email/unsubscribe`, `POST /email/resubscribe`; signed-in switch `GET|PATCH /me/marketing-email`. Retries also skip people who unsubscribed since. Service notices are labelled as such and are not marketing. Table `email_suppressions` (main database). |
| Deletion | Security → **Privacy and your data**: request deletion of your own account, or (company admin) the whole company. Requires the password, a reason is optional, consequences are spelled out, a confirm box must be ticked. Owner console → **Privacy requests**: approve / refuse (refusal needs a reason) / mark done. Approving a personal request deletes the sign-in and personal links immediately; business records stay with the company without the name. A company request is approved, the company downloads its data, the owner deletes it with the existing Delete tool, then marks it done. Every step goes to the company's and the platform's audit log. Table `data_deletion_requests` (excluded from company backups so a restore cannot undo a deletion decision). |
| Accessibility | Light-theme focus indicator in the work area raised from brand green (2.8:1, fails WCAG 1.4.11) to deep green #006B2E with a white inner band (6.7:1). All new UI has labels, fieldsets/legends, captions, `aria-modal` dialog and keyboard support. |
| Billing wording | Added: Ribdigi House adds no fee on top of the shown amount; the payer's bank or Mobile Money provider may charge its own (checkout sends the invoice total — verified in `billing_gateway.py`). |

Migration `20261115_0187` (after `20261115_0184`).

## 3. Third-party and integration register

| Service | Purpose | Personal data it gets | Leaves our server | Consent needed | Necessary | Notes / risk |
|---|---|---|---|---|---|---|
| Hosting server (VPS 206.245.166.6) | Runs the app and database | Everything stored | Provider's data centre | No (processor) | Yes | Provider and its location to be named in the privacy policy once confirmed (owner). |
| Off-site backup bucket (Dokploy → S3-compatible) | Nightly whole-database copy | Everything stored | Yes | No (processor) | Yes | Provider chosen by owner; turn on object lock / versioning; confirm encryption at rest. |
| SMTP mail service (platform, and each company's own) | Sign-in codes, notices, documents, receipts | Recipient address, message content | Yes | No for service mail; yes for marketing (now has unsubscribe) | Yes | Name the platform SMTP provider in the policy. |
| Twilio | SMS when a company turns it on | Phone number, message | Yes (USA) | Company's responsibility | Optional | Company-configured credentials. |
| Paystack / Flutterwave | Subscription payments; till Mobile Money through the company's own Paystack | Email, amount, reference; card/wallet details go to the provider only | Yes | No (contract) | Yes for card/MoMo | Card numbers and PINs never reach our server (`billing_gateway.py`). |
| Frankfurter, open.er-api.com | Exchange rates | None | Request only | No | Optional | No personal data. |
| Umami (self-hosted) | Page counts | Pages viewed, no query strings, no cookies | Only to our own Umami | **Yes** (now enforced) | No | Off; analytics server not running. |
| Google Fonts | — | (was: IP address on every page) | — | — | — | **Removed**; font self-hosted. |
| OpenAI | Optional AI chat | None today | No | — | No | Configurable, but the client is not wired in this build: no AI provider is ever called. |
| ZKTeco BioTime / terminals (`/iclock`) | HR clock-in from the company's own terminals | Staff clock events | Company's devices to us | Company's responsibility (employment) | Optional | Fingerprints stay on the terminal; only clock events arrive. |
| Bank feed (`http_json`), webhooks | Company-configured integrations | What the company chooses to send/receive | To the company's own endpoints | Company's responsibility | Optional | Secrets encrypted; URLs validated. |
| Let's Encrypt | TLS certificates | None | — | No | Yes | — |
| maps.google.com link (bakery delivery address) | Opens a map on click | The address, only when a user clicks | On click only | No | Optional | User-initiated link, not loaded automatically. |
| npm runtime packages | next, react, react-dom only | — | — | — | Yes | No analytics/ads/chat SDKs present. |

No advertising trackers, chat widgets, CRM integrations, social login providers or embedded third-party
media were found. Nothing was removed besides Google Fonts and the dead analytics default.

## 4. Media and licensing register

| Asset | Source | Licence | Attribution | Commercial use |
|---|---|---|---|---|
| `public/brand/*.png`, `app/icon.png`, `app/apple-icon.png`, favicons, `backend/app/branding/*` | Ribdigi House's own logo and marks | Owned by Ribdigi House | None | Yes |
| `public/fonts/plus-jakarta-sans-*.woff2` | Plus Jakarta Sans (Tokotype), from Google Fonts | SIL Open Font License 1.1 (`public/fonts/PlusJakartaSans-OFL.txt`) | Licence file kept with the font | Yes |
| `components/DeskIcon.tsx` and other inline SVG icons | Drawn in-house (single-path line icons) | Owned | None | Yes |

No stock photos, stock video, embedded videos or third-party icon sets ship in the app. Marketing media
(flyers, films, AI-generated imagery) live outside the app and are not covered here; the owner should keep a
register for those (AI-generated assets: record the tool and its terms).

## 5. Data minimisation (forms)

| Form | Required | Optional | Assessment |
|---|---|---|---|
| Sign-in | company (admin door), email/username, password | 2FA code | Minimal. |
| User create | name, email, role, password | phone, username, branch, department | Necessary for access control. |
| Customer / supplier | name | phone, email, address, category, code, GPS, credit terms | Optional fields are business choices; GPS only for field-sales routes. |
| Hotel guest / registration card | name | ID type/number, contact, marketing consent (off by default) | ID details are a hotel practice; the company decides. |
| HR staff file | name and pay basics | statutory numbers, bank/MoMo details, documents | Needed for payroll; confidential documents limited to HR managers. |
| Deletion request (new) | scope, password | reason | Minimal. |

**PARTIAL:** each desk's forms were reviewed by structure, not field by field against each company's lawful
need. Companies are the controllers for these records; Ribdigi House should give companies guidance on what
they need to collect (owner task).

## 6. Results

| # | Requirement | Status | Evidence / note |
|---|---|---|---|
| 1 | Privacy Policy | PARTIAL | Written and live in code; needs legal review, hosting/SMTP/backup provider names, DPC registration status. |
| 2 | Terms of Service | PARTIAL | Written; commitments (5-working-day reply, 30-day notice, mediation in Accra, 30-day export window) need owner/legal sign-off. |
| 3 | Refund Policy | PARTIAL | Written without a blanket no-refund clause; the 14-day first-payment refund and timelines are proposals for the owner to confirm. |
| 4 | Cookie Policy | PASS | Lists only real storage; status line follows the build config. |
| 5 | Consent banner | PASS | Equal buttons, analytics blocked before consent, choice stored with version and time, Cookie settings link everywhere. Banner hidden while no optional category exists (by design). Unit tests `lib/consent.test.ts`. |
| 6 | Form consent | PASS | Renewal agreement unticked and required only for renewal; hotel marketing consent optional and off; no forms force marketing consent. No public lead/newsletter/contact forms exist (N/A). |
| 7 | Data minimisation | PARTIAL | See section 5. |
| 8 | Third-party audit | PASS | Section 3. Google Fonts removed. |
| 9 | Dark patterns | PASS | Renewal off is one click; trial cannot convert silently; price-change re-consent; cookie reject as easy as accept; deletion request available in the app. No countdowns or fake urgency found. |
| 10 | No hidden fees | PASS | Price, currency, period and VAT shown before consent; checkout charges the invoice total; no surcharge in code. |
| 11 | No fake reviews | PASS | No testimonials, ratings or customer logos in the app. (Marketing site/materials not in scope.) |
| 12 | No unsupported claims | PASS | No guarantees, uptime or certification claims found in the app; legal pages avoid them. |
| 13 | Alt text and semantics | PARTIAL | Every `<img>` has alt; no icon-only button lacks a name (scripted check). Heading order and screen-reader flow not tested with a screen reader. |
| 14 | Colour contrast | PARTIAL | New UI passes (banner 12.4:1, legal text 17:1, footer 5.9:1). Focus indicators fixed. **Open:** brand green #4AB012 is used as text on light backgrounds in places and as the background of some buttons with white text (2.8:1, fails 4.5:1). Fixing changes the brand look; see section 7. |
| 15 | Keyboard | PARTIAL | New dialog traps focus, closes on Escape, returns focus. Whole-app keyboard walk-through not done in a browser. |
| 16 | Business details | PASS | Name, address, phone, WhatsApp and email from existing published details on the legal pages. No registration numbers invented. |
| 17 | Children | PASS | Policy states business users only and the company's controller duty for minors in its records; no age gate added to business forms. |
| 18 | Unsubscribe | PASS | Signed links, one-click headers, suppression applied on send and retry, preference switch, service/marketing split. Tests in `test_privacy_unsubscribe_deletion.py`. |
| 19 | Media licensing | PASS (app) | Section 4; marketing media outside scope. |
| 20 | Deletion | PASS | Password re-check, consequences shown, owner review, tenant isolation (another company gets 404), audit trail, records kept where required. Tests in `test_privacy_unsubscribe_deletion.py`. |
| 22 | Security | PASS | Unsubscribe tokens HMAC-signed and compared in constant time; header-injection guard on new email headers; deletion endpoints scoped to the signed-in company; deciders limited to owner/platform admin; no personal data added to logs. |

## 7. Needs the owner or a lawyer

1. **Data Protection Commission:** confirm whether Ribdigi House is registered as a data controller (and
   processor) with the DPC as Act 843 requires, and add the registration status to the privacy policy.
2. Name the hosting, SMTP and backup storage providers and their countries in the privacy policy.
3. Confirm the Terms commitments and Refund Policy numbers (section 6, rows 2–3).
4. Retention periods for accounting and tax records: confirm the period under Ghana law (Income Tax Act,
   VAT Act, Companies Act) and state it in the policy instead of "as long as Ghana law requires".
5. Health-type records (pharmacy, any clinic use) and staff data are sensitive under Act 843; confirm the
   wording and safeguards with a professional before marketing those desks.
6. **Brand contrast:** choose either (a) dark text (#10211B, 5.9:1) on green buttons, or (b) deep green
   #006B2E (6.7:1 with white text) for buttons and green text on light backgrounds. Then it can be applied
   across the app in one pass.
7. When analytics is turned back on, the banner will appear automatically; confirm the Umami server is your
   own and update the cookie policy if anything else is added.

## 8. Tests

- Backend: `tests/test_privacy_unsubscribe_deletion.py` (7 tests: link signing, marketing send with unsubscribe
  headers, suppression on preview/send, service notice still delivered, tampered link refused, signed-in switch,
  personal deletion with password check and audit, company deletion admin-only and tenant-isolated, cancel).
  Existing Email center, backup coverage and Alembic graph suites pass (head pin moved to 0187).
- Frontend: `lib/consent.test.ts` (3 tests) plus all 121 existing `lib/*.test.ts`; TypeScript clean; production
  build passes with the new routes.
- Not done: manual browser pass with keyboard and screen reader; contrast scan of every screen; live production
  check after deploy.
