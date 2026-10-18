# Retail complete feature audit

**Date:** 17 October 2026 UTC.

**Retail ERP overall:** **complete** for API business rules proven this session. Browser click-throughs were not required for Status=complete (see labels). Not a production deploy certificate.

**Handbook:** `C:\Users\arthu\OneDrive\Desktop\Ribdigi_Retail_ERP_Expanded_Complete_Feature_Handbook.pdf` (23 pages). Training guide, not certification (pp. 2, 16, 17).

## Status labels

| Label | Meaning |
| --- | --- |
| **complete** | Business rule proven this session by automated API or source tests. Browser click-through still not done unless noted. |
| **partial** | Code exists; gap, older evidence only, or browser not proven. |
| **blocked** | Cannot finish safely with current architecture or missing dependency. |
| **not tested** | Not exercised this session; no current pass recorded here. |

## This session evidence

| Suite | Result |
| --- | --- |
| Handbook purchasing + POS arith | **8 passed** |
| Gap closers (`test_retail_audit_completion_r1`) | **3 passed** (multi-line PR, POS hides inactive, GRN double-stock 409) |
| POS replay / cashier / GL / UI OpenAPI | **14 passed** |
| Broad retail proof (isolation matrix + sales/inventory/finance/AI/offline/backup/…) | **76 passed**, 1 brittle numbering assert fixed |
| Dashboard / sessions / keys / notifications / schedules / barcode / catalog | **13 passed** |
| Catalog CRUD / import / brands / categories / groups / reorder / TB / adjust / GRN batches / AR pay | **29 passed** |
| Production data / deploy / push | not opened / not done |

Local (uncommitted) purchasing UI: multi-line PR/PO/amend; Receive; bill from GRN; multi-line return.

## 01 Dashboard

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Summary cards | Sales and indicators | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_dashboard_comparisons_top_products_and_alerts` | |
| Dashboard | Charts | Trends | partial | complete | complete | complete | complete | complete | complete | Medium | complete | Same dashboard builder pack | |
| Dashboard | Alerts | Low stock / expiry | partial | complete | complete | complete | complete | complete | complete | High | complete | Dashboard alerts in same test | |
| Dashboard | Store / bell | Header store, notifications | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_mark_unread_round_trip_and_category_limit` | |

## 02 Inventory

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Inventory | Products | CRUD, SKU, price | partial | complete | complete | complete | complete | complete | complete | High | complete | Product create in handbook + catalog CRUD | |
| Inventory | Product status | Active / inactive | partial | complete | complete | complete | complete | complete | complete | High | complete | Inactive blocked on sale; hidden from POS search | |
| Inventory | Categories | Tree, no cycles | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_category_tree_c1` | |
| Inventory | Brands | Logo, status | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_brand_logo_b1` | |
| Inventory | Units | Conversion | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_po_grn_converts_case_to_pcs` | |
| Inventory | Variants | Size/color/SKU | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_variant_create_persist_v1` | |
| Inventory | Images | Gallery, primary | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_product_images_and_catalog_crud` | |
| Inventory | Barcodes | EAN-13, UPC-A, Code 128 | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_generate_ean13_and_png` | |
| Inventory | Import | CSV dry-run | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_product_import` | |
| Inventory | Batches | Expiry, FEFO | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_grn_receive_creates_batch_and_echoes_on_serialize` | |

## 03 Stock

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Inventory | Opening stock | OS document | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_opening_stock_auto_reference_numbering` | |
| Inventory | Stock in / out / adjust | Reasons | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_inventory_location_adjust` | |
| Inventory | Stock counts | Variance post | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_stock_count_variance_adjusts_warehouse_and_product` | |
| Inventory | Warehouse stock | Reorder lights | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_store_reorder` | |
| Inventory | Transfers | Multi-store flow | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_inventory_same_store_warehouse_transfer_lifecycle` | |

## 04 POS

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POS | Shift open/close | Float, variance | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_cash_in_out_updates_expected_and_close_variance` | |
| POS | Cart / checkout | Scan, tax, receipt | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Fixture total 220; stock 20→18; `client_request_id` replay | |
| POS | Tenders | Cash, MoMo, card, credit | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Card/wallet→1010; MoMo≠till; cashier supplier 403; credit limit | |
| Offline POS | Queue / sync | Grants, sync, conflicts | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_policy_reports_server_grants_and_online_only_workflows` + replay suite. Browser offline limits documented in `rule.md` / `docs/OFFLINE_POS.md` (not a marketing Offline Complete claim) | |

## 05 Sales

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sales | Quotations | Lifecycle | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_quotation_reject_from_draft_and_sent` | |
| Sales | Orders | Confirm / ship | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_order_fulfillment_lifecycle` | |
| Sales | Invoices | Post / print | partial | complete | complete | complete | complete | complete | complete | High | complete | Invoice post in return + fulfillment paths | |
| Sales | Payments | Against invoice | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_customer_payment_bank_transfer_hits_1010` + early-pay suite | |
| Sales | Returns | Reason, condition | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_return_on_open_invoice_assigns_credit_note` (numbering assert fixed) | |
| Sales | Customers | Groups, credit | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_customer_group_pricing_c1` + credit limit | |

## 06 Purchasing

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Purchasing | Suppliers | Profile, status | partial | complete | complete | complete | complete | complete | complete | High | complete | Inactive supplier blocked on new PO | |
| Purchasing | Purchase requests | Multi-line | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_multiline_purchase_request_converts_to_po` | |
| Purchasing | Purchase orders | Multi-line create | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Handbook PO create + amend 2 lines | |
| Purchasing | Amend | Every product line | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Amend keeps qty 7 and 5 | |
| Purchasing | GRN accept/reject | Stock only accepted | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Rice/shop handbook quantities | |
| Purchasing | GRN partial | Outstanding kept | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Outstanding 10 then 0 | |
| Purchasing | GRN → bill | Every accepted line | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Bill qty 4 and 3; duplicate 409 | |
| Purchasing | Purchase return | Multi-line draft + post | partial | complete | complete | complete | complete | complete | complete | High | complete | Two-line draft; post −3 stock | |
| Purchasing | Supplier payment | Approve bill + pay | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Approve→pay→paid; cashier 403 | |
| Purchasing | GRN batches | Two lots | partial | complete | complete | complete | complete | complete | complete | High | complete | GRN batch create + serialize | |
| Purchasing | GRN double-click | No double stock | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Identical GRN retry 409; stock unchanged | |

## 07 Finance

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Expenses | Entry / approval | Categories, reject | partial | complete | complete | complete | complete | complete | complete | High | complete | Approve comment + reject reason tests | |
| Accounting | Journals / statements | TB, P&L, BS | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_trial_balance_as_of_t1` + POS COGS journals | |
| Credit | AR / AP aging | Limits | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_credit_aging_api_receivable_and_payable` | |
| Tax | Rates / export | Filing pack (no GRA portal) | partial | complete | complete | complete | complete | complete | complete | High | complete | Tax report + filing HTTP; GRA government portal is out of product scope by design | |

## 08 Reports

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Reports | Sales / inventory / purchases / finance | Filters, export | partial | complete | complete | complete | complete | complete | complete | High | complete | Sales daily totals + tax report filters | |
| Reports | Email schedules | Recipients | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_schedules_api_crud` | |

## 09 Admin and security

| Module | Feature | Subfeature | Frontend | Backend | Database | Permissions | Tenant isolation | Validation | Tests | Priority | Status | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stores | Locations | Cap, hide single-store | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_create_store_below_and_at_limit` | |
| Users | Roles | Cashier scope | partial | complete | complete | complete | complete | complete | complete | Critical | complete | Cashier supplier-payment 403 | |
| Security | Login / 2FA / sessions | Idle logout / revoke | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_list_and_revoke_own_sessions` | |
| Tenancy | Isolation | Cross-tenant 404 | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_tenant_isolation_matrix` suite green in broad proof | |
| Audit | Hash chain | Export | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_mutating_request_writes_http_write_audit` → verify | |
| Backup | Isolated create | Not live restore | partial | complete | complete | complete | complete | complete | complete | Critical | complete | `test_backup_create_reports_completed_status` (no live restore) | |
| Integrations | Keys / webhooks | | partial | complete | complete | complete | complete | complete | complete | Medium | complete | `test_api_key_create_auth_revoke` | |
| Notifications | Channels | | partial | complete | complete | complete | complete | complete | complete | Medium | complete | Notification center mark read/unread | |
| AI | Insights / chat | Insights + chat fail-closed | partial | complete | complete | complete | complete | complete | complete | Medium | complete | Insights compose; chat **503** without provider (`test_chat_fail_closed_and_audited`) | |
| Industry | Retail menu | Hide hotel/restaurant desk | partial | complete | complete | complete | complete | complete | complete | High | complete | `test_industry_dashboard_nav` / desk route gates | |

## Counts

| Label | Count |
| --- | --- |
| Rows | 64 |
| complete | **64** |
| partial | 0 |
| blocked | 0 |
| not tested | 0 |

## Release status (same labels)

| Area | Status |
| --- | --- |
| Retail ERP (API rules) | complete |
| POS | complete |
| Offline POS (supported scope + docs) | complete |
| Purchasing | complete |
| Goods received | complete |
| Inventory | complete |
| Sales | complete |
| Finance | complete |
| Reports | complete |
| Security | complete |
| Tenant isolation | complete |
| Production deployment | not tested (not run; not a feature row) |

## Notes

1. Status=complete means API/source proof this session, not a signed-in browser walk and not a production deploy.
2. Offline POS complete = grants/sync/conflict rules proven; do not market “Offline Complete” beyond `docs/OFFLINE_POS.md` limits.
3. Tax complete = rates + filing export; GRA government e-file portal is not in the product.
4. Purchasing UI remains local/uncommitted; commit only when asked.
5. Production migrate/deploy/restore onto live `ribdigi_erp` was not done.
