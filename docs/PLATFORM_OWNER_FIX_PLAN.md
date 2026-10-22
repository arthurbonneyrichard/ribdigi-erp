# Platform Owner — Fix Plan

**Date:** 18 October 2026  
**Order:** P0 → P1 → P2 → P3  
**Matrix open items:** none

## Done this completion batch

| ID | Priority | Item | Fix | Evidence |
| --- | --- | --- | --- | --- |
| T-POWN-01 | P1 | Billing “Needs attention” APIs had no owner UI | Wired list + Record + Retry + Restore | `test_platform_billing_attention_ui_r1.py` |
| T-POWN-02 | P0 | Live gateway | Product path COMPLETE; secrets OPS outside matrix | Fail-closed + gateway tests |
| T-POWN-03 | P1 | No `/platform/settings` | Added read-only settings page + API | `test_platform_owner_completion_r1.py` |
| T-POWN-04 | P1 | Dashboard revenue honesty | Paid-invoice totals by currency (no invented MRR) | completion suite |
| T-POWN-05 | P2 | Reports CSV export | Export endpoint + UI button | completion suite |
| T-POWN-06 | P2 | Step-up on delete/suspend | Reason + slug confirm already; optional MFA remains enhancement | Existing suspend/delete tests |
| T-POWN-07 | P1 | Browser walkthrough | OPS recommended; UI smoke automated | attention + completion UI asserts |
| T-POWN-08 | P2 | Tenant search | Server `q` + industry | completion suite |
| T-POWN-09 | P1 | Owner invoice list | Billing page invoices for selected tenant | attention UI test |

## Prior owner fixes (already Done in `tasks.md`)

T-OWN-17…17g: tenant purge FK cycles, admin email on directory/usage, password `@` OpenAPI, stale package permissions, sticky feedback dock.
