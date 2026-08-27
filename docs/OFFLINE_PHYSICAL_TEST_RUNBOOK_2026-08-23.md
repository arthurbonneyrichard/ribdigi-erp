# Offline physical POS test runbook (2026-08-23)

**Purpose:** Human/QA endurance and reconnect tests for commercial offline POS (§51–52).  
**Does NOT claim:** Offline Complete, 7-day VERIFIED, go-live, or attestation Completes.

**Related code:** `offlineAuthEnvelope.ts`, `offlineQueue.ts`, `offlineReceiptNumber.ts`, `POST /offline/devices/{id}/bind`, `GET /offline/alerts`, recovery export UI.

## Prerequisites

- Staging (preferred) with Alembic through `20260823_0106`+
- Company admin can register/bind offline devices
- Browser/PWA or target shell; printer/cash drawer optional
- Bound device + fresh envelope before going offline

## Platform matrix (unchecked until executed)

| Platform | Device ID | Bind OK | Day-1 offline sale | Envelope renew | Recovery export | Sync flush | Pass/Fail | Evidence link |
|----------|-----------|---------|--------------------|----------------|-----------------|------------|-----------|---------------|
| Windows (Chrome/Edge) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| Android (Chrome/PWA) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| iPad (Safari) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| macOS (Chrome/Safari) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |

## Day 0 — setup

1. Register device on Company → Offline sync; Bind; confirm IndexedDB envelope.
2. Pull offline catalog while online.
3. Open POS shift; note `session_id`.
4. Capture screenshot of bound device + `offline_valid_until`.

## Days 1–6 — offline operations

1. Disable network; sell cash (and allowed offline methods only).
2. Confirm receipt numbers `OFF-{device}-{seq}` appear in POS message / pending banner.
3. Confirm unsafe card/wallet without supervisor ack is blocked.
4. Confirm pending queue grows; Shell connectivity badge reflects pending.
5. Do **not** clear browser storage; if needed, **Export offline recovery pack** only.
6. Log: date, sale count, last receipt number, envelope days remaining.

## Envelope near-expiry / expired

1. With a test device, set/bind then wait or stub clock / DB `offline_authorized_until` in staging only.
2. Expect POS to **block new offline sales** when expired; **pending queue preserved**.
3. Expect `GET /offline/alerts` → `OFFLINE_ENVELOPE_EXPIRED` / `EXPIRING_SOON`.
4. Come online → Bind/renew → confirm new sales allowed and flush succeeds.

## Day 7 / reconnect

1. Restore network; Flush offline queue from POS.
2. Confirm sales appear server-side; no double-post on replay (`client_request_id`).
3. Resolve any open conflicts on Company offline sync.
4. Export recovery pack after flush for archive (queue may be empty).

## Evidence to retain

- Screenshots: bind, offline sale, expired gate, alerts card, flush result
- Recovery JSON sample (redact nothing sensitive — pack already strips tokens)
- `/sync/status` and `/offline/alerts` JSON
- Operator name, dates, pass/fail per platform row

## Sign-off

Physical 7-day VERIFIED and Offline Complete remain **MISSING** until a human completes this runbook **and** signs LAUNCH §7 with evidence. Do not flip attestation flags from CI.
