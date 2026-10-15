# Till print agent (stub)

This process runs **on the till PC or Android termux/python**, not in the browser.

The browser **cannot** enumerate every OS printer and **cannot** silently send
to kitchen + bar + receipt at once. Pair this agent, or register a private
network IP on the server allowlist.

## Pair (Company Admin)

1. Sign in as Company Admin (or a role with `printers:write`).
2. Open **Settings → Printers**.
3. Enter a till name and click **Issue till pairing code**.
4. On the till:

```bash
export RIBDIGI_API_BASE=https://YOUR-ERP/api/v1
python agent.py pair ABCD1234 "Front till"
export RIBDIGI_AGENT_TOKEN=rdp_...   # shown once
python agent.py
```

5. In Printers, add a destination with connection **Paired till agent** and
   assign purposes (`customer_receipt`, `kitchen`, `bar`, `invoice`).

Do **not** commit tokens or `.env` files.

## Offline sale journal

`python agent.py` also listens on `127.0.0.1:8765` (override with `RIBDIGI_OFFLINE_PORT`). Point of Sale writes each queued sale there. The file is outside the browser:

- `RIBDIGI_OFFLINE_JOURNAL`, or
- `%LOCALAPPDATA%\Ribdigi\pos-offline-journal.json` on Windows

`python agent.py journal` runs only that listener. It does not need `RIBDIGI_AGENT_TOKEN` and it does not upload the sale. Clearing site data does not delete the file. Recovery works only when this process was running at the time the sale was saved, and the file is still on this PC. A private window with no journal file cannot recover the sale. The browser device id is still not strong device binding.

## Hardware still required

This stub prints to stdout and marks jobs `printed`. Real ESC/POS, CUPS, or
Android USB printing is a local install step on the till. Until that is wired,
use **Browser print dialog** fallback on POS.
