# Till lock, cashier passcodes and the restaurant digital menu

## Till lock

Applies to the retail POS (`/pos`) and the restaurant till (`/restaurant/till`). The rest of the ERP is not locked.

- The till locks after 60 seconds with no mouse, keyboard or touch. The **Lock** button locks at once.
- Each person has their own 6-digit passcode. Staff screens (Users, Restaurant Staff) create, change, reset and turn off passcodes. Repeated digits and runs like `123456` are refused.
- A passcode unlocks as that person. On till paths the server then acts as them, so shifts, sales, audit rows and permissions belong to the person at the till.
- The cashier identity reaches till paths only (`pos_lock.OPERATOR_PATHS`). An admin's passcode on a cashier's till does not open admin screens.

### When enforcement starts

A passcode is the only way through the lock: no account password, no link back to the dashboard and no sign-out. Log out on a locked till returns to the lock screen, so signing out needs the passcode first. So the lock starts when a company has at least one active passcode, and the server then refuses till writes with `423 POS_LOCKED`. Before that, tills do not lock and keep selling under the signed-in account, so a deploy cannot strand a shop. **Give every cashier a passcode before setting the first one in a busy shop.** Someone without a passcode cannot use the till until a manager gives them one.

### Taking over a till

Another cashier enters their passcode on the lock screen. The old stint ends (`pos_operator_sessions.end_reason = switched`) and a new one starts. Each cashier has their own shift, so the new cashier opens or resumes theirs.

If the first cashier left a sale, the new cashier must choose:

- **Take over this sale**: it is recorded under the new cashier, with `started_by_user_id` naming the first.
- **Keep it for them**: the sale is set aside on that device and comes back when they unlock.

Both choices are audited as `pos_sale_handover`.

### Security

| Control | Detail |
| --- | --- |
| Storage | bcrypt, plus a keyed HMAC lookup. The HMAC is what makes "unique in the company" possible. Set `POS_PASSCODE_PEPPER` in production: without it the key comes from `JWT_SECRET_KEY`, and rotating that secret means reissuing every passcode. |
| Wrong passcodes | 5 on a till locks that till for 5 minutes. 15 on an account locks it for 15 minutes, which stops a guesser who keeps changing the till id. |
| Refresh or direct navigation | A page that starts locked does not mount. The server decides, not the browser. |
| Switching off the browser timer | The server locks a stint after 150 seconds with no activity ping. |
| Audit | `pos_locked`, `pos_unlocked`, `pos_unlock_failed`, `pos_unlock_denied`, `pos_cashier_switched`, `pos_sale_handover`, `pos_passcode_*`. |

### Offline

Only the last cashier on a till can unlock offline, using a PBKDF2 check saved on that device at their last online unlock. Switching cashier needs a connection. If no check is saved, an offline till does not auto-lock, because nobody could open it again and selling must not stop. Queued sales stay with the cashier who made them and sync when that cashier is at the till.

## Cashier reports

- Retail: Reports, **Cashier performance** (`GET /reports/sales/cashiers`, `/transactions`).
- Restaurant: Reports, **Cashier performance** section (`GET /restaurant/reports/cashiers`, `/transactions`).

Each desk reads its own tables. Sales before this release have no till name.

## Digital menu

Restaurant only, at `/restaurant/menu`. Editing needs `inventory:write`, and the restaurant job gate stops waiters, cashiers and kitchen staff.

- A menu item points at a dish, so **name, price, description and photo are the till's own**. Changing a price here changes the till.
- Guests use `/menu/<token>` and TVs use `/menu/<token>/board`. No login. The menu must be published first.
- `<token>` is random, so a menu cannot be found from a company name or id. **New QR code** replaces it and every printed code stops working. Editing the menu never changes it.
- The public payload is built field by field in `restaurant_menu._guest_payload`. Do not widen it with whole rows.
- Phones refresh every 60 seconds and the board every 20. Both use an ETag, so an unchanged menu costs almost nothing.
- "Unavailable" is the restaurant's sold-out list, shared with the till.
