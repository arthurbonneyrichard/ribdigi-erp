# Printer routing and till agents

Company == Tenant in this product. Printers are tenant-scoped (optional store).

## What the browser cannot do

The browser cannot list every OS printer or silently fan-out to kitchen, bar,
and receipt printers. Ribdigi therefore supports:

1. **Browser print dialog** (OS picker) — cashier acknowledges print
2. **Paired local print agent** on the till (desktop or Android with Python)
3. **Network printer** whose host is validated on the server (RFC1918 / loopback / `.local` only)

Queued is **not** Printed. Retry / reprint does **not** create a new sale.
Receipt and invoice numbers are issued by the server even if printers are offline.

## Company Admin setup

1. **Settings → Printers** (permission `printers:write`; Company Admin and Store Manager).
2. Add a friendly name, connection type, store (or all stores), paper, purposes, copies.
3. Enable more than one printer per purpose if needed (kitchen + spare).
4. **Test print** enqueues a job with no sale.
5. Restaurant: on a category or product set optional **prep station** `kitchen` or `bar`. Mixed orders split into separate tickets for the same sale. Prep tickets omit payment details. Retail tenants leave the station empty.

## Cashier / POS

Checkout completes even if printers are down. The sale response includes
`print_jobs` with statuses such as `queued` or `browser_pending`. Use
**Open print dialog** then ack. **Reprint** creates new jobs for the same
`sale_id`.

## Agent install

See `ops/print-agent/README.md`. Tokens are shown once and stored hashed.

## Hardware checks remaining

- Real ESC/POS / CUPS / Android USB output
- Agent service auto-start on Windows/Android
- Latency and paper-out sensors

Automated tests simulate the queue only.
