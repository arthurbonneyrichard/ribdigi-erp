# Commercial tip — Alembic deploy prerequisites (2026-08-23)

**Branch tip context:** `cursor/transfer-genemonyuglaze-gate-427f` commercial hardening (not honesty-pack packaging).  
**Status:** Operator checklist only. **Go-live / production cutover remain NOT READY** (`production_cutover_claimed: false`).

## Apply in order

| Revision | Purpose | Before enabling |
|----------|---------|-----------------|
| `20260823_0106` | Offline auth envelope columns on `offline_devices` | `POST /offline/devices/{id}/bind`, sync push/pull envelope validation |
| `20260823_0107` | `tenants.max_companies_override` | Platform company-entitlement override + plan sync |
| `20260823_0108` | `tenants.max_users_override` | User create/reactivate/import limits + platform user-entitlement |
| `20260823_0109` | `purchase_invoices.warehouse_id` (nullable) | Store-manager PI scope for manual invoices |

```bash
# From backend with production DATABASE_URL
alembic upgrade head
# Or pin explicitly:
alembic upgrade 20260823_0109
```

Confirm chain: `0107.down_revision == 0106`, `0108.down_revision == 0107`, `0109.down_revision == 0108`.

## Post-migrate smoke (staging)

- [ ] `GET /api/v1/health/ready` healthy
- [ ] Bind offline device → envelope `offline_valid_until` present
- [ ] `PATCH /api/v1/platform/tenants/{id}/company-entitlement` (House)
- [ ] `PATCH /api/v1/platform/tenants/{id}/user-entitlement` (House)
- [ ] Create user at limit → `USER_LIMIT_REACHED`
- [ ] Create company at limit → `COMPANY_LIMIT_REACHED`

## Explicitly not claimed

- Production cutover executed
- Offline Complete / 7-day physical VERIFIED
- Paid billing (ADR-002)
- LAUNCH §7 signed
