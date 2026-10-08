# SaaS subscription billing

This charges a company for using Ribdigi ERP. It is separate from sales, POS, and customer payments. Those flows are unchanged.

No payment gateway is configured in this repository. The default provider is `mock`.

## What works without live credentials

- Platform owner plan catalog, tenant plan assignment, and trial dates.
- Tenant administrator consent, hosted-checkout handoff, invoices, and cancellation of future renewals at `/company/billing`.
- Platform owner plan and tenant billing review at `/platform/billing`: assign a plan, record a matching manual payment, retry an authorized charge, suspend access, and restore access. Restore does not create a charge. An unpaid restored account stays `payment_required`.
- Trial-end reminders use `BILLING_REMINDER_DAYS` (default 7, 3, and 1) and do not create a charge. A provider response of pending leaves the invoice unpaid until a signed webhook confirms success or failure.
- The mock provider can save a sandbox authorization (`mock_auth_…`) and simulate one renewal charge in development and tests. On `/company/billing`, **Save sandbox payment method** appears only while the provider is mock and live charges are off. A return to `?checkout_ref=` does not mark an invoice paid.
- Renewal processing is a Celery job, `process_subscription_renewals`, every `CELERY_BILLING_INTERVAL_MINUTES` (default 60).
- Webhooks are rejected unless the signature matches. A browser return from checkout never marks an invoice paid.
- Duplicate scheduler runs and duplicate webhook ids do not create a second invoice or charge.
- Failed charges retry at most `BILLING_MAX_ATTEMPTS` (default 3), then a grace period, then suspension. Tenant data is not deleted.
- Canceling automatic renewal stops later charges and leaves access through the paid-through date.
- During `payment_required`, `past_due`, and `grace_period`, the tenant status is `grace` (read-only) except subscription billing itself.
- When a trial ends with no authorization, and when a charge fails or grace ends in suspension, the company and the platform owner both get a billing notice. The owner notice names the company and does not include a card number or gateway token.

The mock provider refuses to capture money when `APP_ENV=production`.

## Live Paystack (not enabled here)

Set these only in the server environment. Do not commit them.

- `BILLING_PROVIDER=paystack`
- `PAYSTACK_SECRET_KEY` — secret key, server only
- `FRONTEND_URL` — used as the hosted-checkout return URL

Paystack must support:

- Hosted checkout via transaction initialize
- Reusable `authorization_code` for `charge_authorization`
- Webhook `POST /api/v1/billing/webhooks/paystack` with header `x-paystack-signature` (HMAC-SHA512 of the raw body using the secret key)
- Amounts in minor units (pesewas for GHS) and the same currency as the invoice

The mock webhook is `POST /api/v1/billing/webhooks/mock` with header `x-ribdigi-billing-signature` (HMAC-SHA256 using `BILLING_WEBHOOK_SECRET`).

Until `PAYSTACK_SECRET_KEY` is set, live recurring billing does not run.
