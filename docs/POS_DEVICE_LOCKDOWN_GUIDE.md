# POS Device Lockdown Guide (application + OS)

**Status:** Guidance only — **NOT VERIFIED** on physical hardware in this environment.  
**Scope:** Reduce casual tampering on dedicated POS terminals. This is **not** MDM, DLP, or a substitute for device management.

Ribdigi ERP application controls (already in product):

- Cash-only while offline (card/momo blocked until online confirmation)
- Offline auth envelope expires after ~7 days without reconnect
- Pending sync queue + recovery JSON export (no passwords/tokens)
- Local reset guard when unsynced sales remain (`assertSafeLocalReset`)
- Device heartbeat last-seen (`POST /pos/devices/heartbeat`)

OS lockdown below is **owner/ops responsibility**.

---

## Windows (recommended dedicated POS PC)

1. Create a standard (non-admin) Windows user for cashiers.
2. Set Edge/Chrome as the shell home page to your production POS URL (`https://…/pos`).
3. Optional kiosk: **Assigned Access** (Settings → Accounts → Other users → Set up a kiosk) locked to the browser, or a third-party kiosk shell.
4. Disable guest accounts; require sign-in after sleep.
5. Block USB autorun; prefer barcode scanners in keyboard-wedge HID mode.
6. Keep Windows Update on a maintenance window; never leave an admin session open on the floor.
7. Confirm Ribdigi heartbeat appears under **POS → POS devices (last seen)** after login.

**Not covered:** BitLocker policy, Intune, AppLocker — use your MDM if required by compliance.

---

## Android tablet

1. Use a dedicated work profile or single-purpose device.
2. Install Chrome/Edge; pin the POS URL; enable **Lock task / screen pinning** (or fully managed kiosk via MDM).
3. Disable unknown sources; remove unused apps from the home screen.
4. Keep the tablet plugged in; configure never-sleep while charging if the shift is continuous.
5. Test offline airplane-mode cash sale → reconnect sync before go-live.

---

## iPadOS

1. Use **Guided Access** (Settings → Accessibility → Guided Access) locked to Safari/Chrome on `/pos`.
2. Or Supervised mode + Single App Mode via Apple Business Manager / MDM.
3. Disable iCloud sign-out for the floor Apple ID; use a Managed Apple ID when possible.
4. Test offline + recovery export before marketing offline capability.

---

## macOS (secondary / back-office POS only)

1. Prefer a standard user; avoid admin for cashiers.
2. Full Screen browser on `/pos`; use Screen Time / parental controls only if no MDM.
3. For production retail floors, prefer Windows/Android kiosk hardware over a general Mac.

---

## Verification checklist (Owner)

| Step | Result |
|------|--------|
| Online cash sale | ☐ |
| Offline cash sale queues + syncs once | ☐ |
| Offline card/momo blocked | ☐ |
| Recovery export downloads JSON without tokens | ☐ |
| Heartbeat row updates within ~1 minute online | ☐ |
| Kiosk/Guided Access prevents easy exit to desktop | ☐ |
| 7-day endurance (device left offline) | ☐ NOT RUN until scheduled |

---

## Honesty

Shipping this document does **not** make **POS Device Lockdown** COMPLETE. Mark COMPLETE only after a named device SKU passes the verification checklist above and ops retains screenshots/notes.
