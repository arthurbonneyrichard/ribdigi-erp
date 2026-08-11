# Support / Admin ops map (Stage 30 S1)

| File | Role |
|------|------|
| `admin-ops-map.json` | Maps `docs/ADMIN_MANUAL.md` §§7 / 11 / 12 to Stage 26–30 ops packs |

Authoritative MVP doc: `docs/SUPPORT_RUNBOOK_MVP.md` (`backend/tests/test_support_runbook_s1.py`).

Do **not** treat ADMIN_MANUAL UI steps as proof of live PITR / cutover / PagerDuty success. Packaging keeps `live_ops_success_claimed: false`, `support_sla_claimed: false`.
