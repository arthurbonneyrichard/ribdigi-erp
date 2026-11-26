# Printer routing, automatic receipts and till agents

Company == Tenant in this product. Printers are tenant-scoped (optional store).

## How a receipt prints

1. The payment is saved.
2. The screen asks `POST /api/v1/printers/receipts` (`source_type`, `source_id`, this till's id).
   POS sales also queue their job on the server right after the sale is committed.
3. The server builds the receipt from the saved payment and queues one job per receipt printer.
4. A **network** printer is sent to by the server; a **till agent** collects the job within about a second.
5. The on-screen printer shows the real job status. No browser print dialog opens.

Rules:

- No saved, completed payment, no receipt (`409 PAYMENT_NOT_CONFIRMED` / `404`).
- Asking twice returns the same job. **Reprint** makes a new job marked `REPRINT`; it never creates a sale or payment.
- A print failure never changes the payment. **Retry** resends the same job.
- Jobs not collected within 12 hours fail instead of printing days later.

## Connections

| Connection | Use when | Prints by itself |
|---|---|---|
| Paired till agent | Normal choice, and the **only** one for a cloud-hosted ERP. USB, LAN, Bluetooth | Yes |
| Network (server sends) | Only when the ERP server is on the shop's own network | Yes |
| Browser print dialog | No agent. A manual button only | No |

A cloud server cannot reach a printer on a shop's private network.

## Company Admin setup

1. Install and pair the agent: `ops/print-agent/README.md`.
2. **Printers → Network or till agent**: name, connection, how the till reaches it, paper (58 or 80mm), jobs, copies.
3. On each till: **Printers → Automatic receipt printing on this till**: pick its printer, turn automatic printing on or off, Save.
4. **Print test page** reports what the printer answered.
5. Restaurant: set a category or product **prep station** `kitchen` or `bar` for separate tickets.

Without a till choice, a receipt goes to every enabled receipt printer for the store.

## Receipts covered

POS (retail, supermarket, pharmacy, wholesale), layaway payments, restaurant till,
bakery counter, order deposits and trade payments, hotel folio payments, shop sales
and company invoices, gym memberships and shop, FMCG collections and van cash sales,
customer account payments.

Not yet: gym extra fees (lockers, classes), FMCG dispatch settlement, e-commerce
"Payment received", supplier payments (money going out). Sales invoices, bills,
reports and payslips remain documents printed from the browser.

## Hardware checks

Automated tests use an emulated network printer. Before relying on a model, on the
real till: test slip, one cash sale (change), 58/80mm widths, cutter, paper-out,
printer switched off then Retry.
