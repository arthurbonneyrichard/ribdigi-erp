# Tenant Industry Isolation — Retail focus

**Date:** 18 October 2026  

## Provision industries

New companies: **retail | hotel | restaurant** only (`VALID_INDUSTRIES`).

## Retail isolation (enforced)

| Rule | Status | Evidence |
| --- | --- | --- |
| Retail sidebar omits hotel/restaurant floors | COMPLETE | `filterNavForIndustry` + Shell |
| Hotel/restaurant APIs 403 without module | COMPLETE | Industry module allowlist |
| Gift cards retail-only in nav | COMPLETE | `industryNavHrefOk` |
| FMCG/hospital not in `enabled_modules` | COMPLETE | `IMPLEMENTED_INDUSTRY_MODULES` |
| Wholesale desk not provisionable | COMPLETE (intentional) | `canonicalize_industry` → null; trade tests |

## Out of this retail assignment

Pharmacy (legacy), hotel, restaurant, wholesale desks — not re-certified here. Retail matrix does not include their feature rows.
