# Offline 7-day physical evidence template (operator pack)

**Purpose:** Fillable evidence pack for the 7-day offline POS matrix.  
**Does NOT claim:** Offline Complete · **7-day VERIFIED** · go-live · push-delivery Complete.

**Parent runbook:** [`OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`](OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md)  
**Honesty:** Leave **7-day VERIFIED = MISSING** until a human completes every required
platform row, retains evidence links, and signs the sign-off below. CI / Cloud Agents
**cannot** flip VERIFIED in one session.

---

## Cover sheet

| Field | Value |
|-------|-------|
| Staging tenant / company | |
| Operator name | |
| Start date (Day 0) | |
| End date (Day 7 reconnect) | |
| Tip / build SHA under test | |
| Environments (staging URL) | |
| VAPID push enabled? (Y/N — optional) | |
| Wipe poll used as fallback? (Y/N) | |

**Verdict after run (circle one):** NOT RUN · IN PROGRESS · FAIL · PASS (evidence attached)  
**7-day VERIFIED claim authorized?** ☐ No (default) ☐ Yes — only after PASS + sign-off

---

## Platform matrix (copy from runbook; attach evidence links)

| Platform | Device ID | Bind OK | Day-1 offline sale | Envelope renew | Recovery export | Sync flush | Pass/Fail | Evidence link |
|----------|-----------|---------|--------------------|----------------|-----------------|------------|-----------|---------------|
| Windows (Chrome/Edge) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| Android (Chrome/PWA) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| iPad (Safari) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| macOS (Chrome/Safari) | | [ ] | [ ] | [ ] | [ ] | [ ] | | |

Minimum for VERIFIED: **all four platforms Pass** with linked evidence (product may
accept a documented subset only via explicit written waiver — default is all four).

---

## Day log (one row per calendar day offline)

| Day | Date | Platform | Offline sales count | Last receipt `OFF-…` | Envelope days left | Queue depth | Notes / blockers | Evidence link |
|-----|------|----------|---------------------|----------------------|--------------------|-------------|------------------|---------------|
| 0 (setup) | | | — | — | | 0 | Bind + catalog pull | |
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |
| 6 | | | | | | | | |
| 7 (reconnect) | | | flush | | | | Flush + conflict resolve | |

### Day-0 checklist (per platform)

- [ ] Register device · Bind browser · envelope `offline_valid_until` captured
- [ ] Push: registered **or** honest skip/timeout (poll remains) — do not invent delivered
- [ ] Offline catalog pulled while online
- [ ] POS shift opened; `session_id` noted
- [ ] Screenshot: bound device + envelope

### Days 1–6 checklist (repeat daily)

- [ ] Network disabled; cash (allowed) offline sales only
- [ ] Receipt numbers `OFF-{device}-{seq}` visible
- [ ] Unsafe card/wallet blocked without supervisor ack
- [ ] Pending queue grows; Shell badge reflects pending
- [ ] **No** browser storage clear; recovery export only if needed
- [ ] Log row filled (sale count, last receipt, envelope days left)

### Envelope expiry probe (staging only)

- [ ] Expired envelope blocks **new** offline sales; pending queue preserved
- [ ] `GET /offline/alerts` shows expired/expiring
- [ ] Online bind/renew restores sales + flush

### Day-7 reconnect checklist

- [ ] Network restored; Flush offline queue
- [ ] Server sales present; no double-post on `client_request_id` replay
- [ ] Conflicts resolved on Company offline sync
- [ ] Recovery pack exported for archive

---

## Wipe / push optional probes (do not substitute for 7-day)

| Probe | Result | Evidence |
|-------|--------|----------|
| Poll-path wipe (no FCM) per `OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md` | Pass / Fail / Skip | |
| Wipe-via-push staging checklist | Pass / Fail / Skip / Blocked | |

Passing wipe probes ≠ 7-day VERIFIED ≠ Offline Complete.

---

## Evidence inventory (attach or link)

| # | Artifact | Path / URL | Redaction OK? |
|---|----------|------------|---------------|
| 1 | Bind screenshot | | Y — no secrets in UI |
| 2 | Offline sale screenshot | | Y |
| 3 | Expired gate screenshot | | Y |
| 4 | Alerts card / `/offline/alerts` JSON | | Y |
| 5 | Flush result / `/sync/status` JSON | | Y |
| 6 | Recovery pack JSON sample | | Pack already strips tokens |
| 7 | Day log export (this file filled) | | Y |

---

## Sign-off

| Role | Name | Date | Signature / initials |
|------|------|------|----------------------|
| Operator (executed matrix) | | | |
| Reviewer (evidence checked) | | | |
| Product (VERIFIED authorization) | | | |

**Attestation flags after sign-off (manual product process only):**

- `seven_day_verified_claimed` → flip only after PASS + product authorization  
- `offline_complete_claimed` → **still separate** (`OFFLINE_COMPLETE_ATTESTATION.md`)  
- Do **not** flip from CI, Cloud Agents, or this template alone

---

## Related

- Runbook: `docs/OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`
- Poll alternative: `docs/OFFLINE_WIPE_POLL_LOCAL_ALTERNATIVE.md`
- Push staging: `docs/offline_wipe_push_staging_checklist.md`
- Go-live roll-up §3E: `docs/GO_LIVE_READINESS_CHECKLIST.md`
