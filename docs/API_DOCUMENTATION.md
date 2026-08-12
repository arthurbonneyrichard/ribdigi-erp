# API Documentation

## RIBDIGI BUSINESS ERP — MVP API Reference

**Version:** 1.0.0  
**Base URL:** `https://api.ribdigi.com/v1`  
**Protocol:** REST / JSON  
**Authentication:** JWT + OAuth2  
**Backend:** FastAPI  
**Last Updated:** August 2026

---

## Table of Contents

1. [API Standards](#1-api-standards)
2. [Authentication](#2-authentication)
3. [Tenant Management](#3-tenant-management)
4. [User Management](#4-user-management)
5. [Inventory & Products](#5-inventory--products)
6. [Purchasing & Suppliers](#6-purchasing--suppliers)
7. [Sales & Customers](#7-sales--customers)
8. [Point of Sale (POS)](#8-point-of-sale-pos)
9. [Expense Management](#9-expense-management)
10. [Accounting](#10-accounting)
11. [Credit Management](#11-credit-management)
12. [Tax Management](#12-tax-management)
13. [Multi-Store Management](#13-multi-store-management)
14. [Reports](#14-reports)
15. [Notifications](#15-notifications)
16. [AI Business Assistant](#16-ai-business-assistant)
17. [Webhooks](#17-webhooks)
18. [Caching](#18-caching-stage-6-p2)
19. [Rate Limits](#19-rate-limits)
20. [Error Codes](#20-error-codes)

---

## 1. API Standards

Stage 19 A1 proves live standards under `/api/v1` — `test_api_standards_a1.py` (BR-18.6). Stage 19 D1 fidelity sync: `docs/STAGE_19_FIDELITY.md` (`test_stage19_fidelity_d1.py`) — BR-18–20 + LAUNCH §5. Stage 20 D1 AI fidelity sync: `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`) — BR-21. Stage 21 D1/H21x tenant/org/dashboard fidelity + exit: `docs/STAGE_21_FIDELITY.md` (`test_stage21_fidelity_d1.py`), `docs/STAGE_21_EXIT_CRITERIA.md`, ADR-048 (`test_stage21_exit_h21x.py`) — BR-1–4. Stage 22 D1/H22x expenses/ledger/credit/tax fidelity + exit: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`), `docs/STAGE_22_EXIT_CRITERIA.md`, ADR-050 (`test_stage22_exit_h22x.py`) — BR-9–12. Stage 23 D1/H23x reports-dimension & MVP-gate fidelity + exit: `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`), `docs/STAGE_23_EXIT_CRITERIA.md`, ADR-052 (`test_stage23_exit_h23x.py`) — BR-14 (historical open ADR-051). Stage 24 D1/H24x commerce & ops gate fidelity + exit: `docs/STAGE_24_FIDELITY.md` (`test_stage24_fidelity_d1.py`; N1 `test_document_numbering_n1.py`; G1 `test_commerce_gate_closure_g1.py`; O1 `test_ops_ai_gate_closure_o1.py`), `docs/STAGE_24_EXIT_CRITERIA.md`, ADR-054 (`test_stage24_exit_h24x.py`) — BR-20.4 (historical open ADR-053 / `docs/STAGE_24_PLAN.md`). Stage 25 D1/H25x actuals → AI → insights fidelity + exit: `docs/STAGE_25_FIDELITY.md` (`test_stage25_fidelity_d1.py`; P1 `test_ai_purchases_analysis_p1.py`; X1 `test_ai_cross_domain_x1.py`; B1 `test_ai_business_insights_b1.py`; U1 `test_ai_ui_fidelity_u1.py`), `docs/STAGE_25_EXIT_CRITERIA.md`, ADR-056 (`test_stage25_exit_h25x.py`) — BR-21.2 / 21.11 / 21.12 (historical open ADR-055 / `docs/STAGE_25_PLAN.md`). Stage 26 closed (ADR-058): Production Platform & Ops Fidelity — `docs/STAGE_26_PLAN.md`, `docs/STAGE_26_EXIT_CRITERIA.md` (historical open ADR-057; `test_stage26_open.py`). Stage 26 M1 monitoring scrape/alerts/log-ship: `ops/prometheus/`, `ops/logging/`, `docs/OPS_MONITORING_MVP.md` (`test_ops_monitoring_m1.py`). Stage 26 W1 WAL/PITR + S3 offsite strategy: `docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/`, `ops/backup/` (`test_wal_pitr_w1.py`). Stage 26 K1 Kubernetes/Helm deploy fidelity: `helm/ribdigi/`, `k8s/`, `docs/K8S_DEPLOY_MVP.md` (`test_k8s_deploy_k1.py`). Stage 26 C1 load capacity evidence: `docs/LOAD_CAPACITY_MVP.md`, `backend/loadtest/` (`test_load_capacity_c1.py`). Stage 26 D1 production platform fidelity: `docs/STAGE_26_FIDELITY.md` (`test_stage26_fidelity_d1.py`) — BR-16 / NFR ops evidence lock; public API contracts unchanged. Stage 26 H26x exit + freeze: `docs/STAGE_26_EXIT_CRITERIA.md`, ADR-058 (`test_stage26_exit_h26x.py`). Stage 27 closed (ADR-060): Commercial MVP Release Fidelity — `docs/STAGE_27_PLAN.md`, `docs/STAGE_27_EXIT_CRITERIA.md` (historical open ADR-059; `test_stage27_open.py`) Stage 27 B1 offsite upload (`test_backup_offsite_b1.py`); P1 PgBouncer (`docs/PGBOUNCER_MVP.md`, `test_pgbouncer_p1.py`); S1 security scan (`docs/SECURITY_SCAN_MVP.md`, `test_security_scan_s1.py`); L1 launch cert (`docs/LAUNCH_CERT_MVP.md`, `test_launch_cert_l1.py`). Stage 27 D1 release fidelity: `docs/STAGE_27_FIDELITY.md` (`test_stage27_fidelity_d1.py`). Stage 27 H27x exit + freeze: `docs/STAGE_27_EXIT_CRITERIA.md`, ADR-060 (`test_stage27_exit_h27x.py`). Stage 28 open (ADR-061): Staging Certification Fidelity — `docs/STAGE_28_PLAN.md` (`test_stage28_open.py`). Stage 28 R1 PITR drill pack: `docs/PITR_DRILL_PACK_MVP.md` (`test_pitr_drill_pack_r1.py`). Stage 28 G1 staging GHA: `docs/STAGING_GHA_MVP.md` (`test_staging_gha_g1.py`). Stage 28 A1 Grafana pack: `docs/GRAFANA_PACK_MVP.md` (`test_grafana_pack_a1.py`). Stage 28 C1 1000-VU cert pack: `docs/LOAD_CERT_PACK_MVP.md` (`test_load_cert_pack_c1.py`). Stage 28 D1 staging certification fidelity: `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`). Stage 28 H28x exit + freeze: `docs/STAGE_28_EXIT_CRITERIA.md`, ADR-062 (`test_stage28_exit_h28x.py`). Stage 29 open (ADR-063): Operator Hardening & Production Cutover Fidelity — `docs/STAGE_29_PLAN.md` (`test_stage29_open.py`). Stage 29 V1 pen-test pack: `docs/PENTEST_PACK_MVP.md` (`test_pentest_pack_v1.py`). Stage 29 B2 PgBouncer soak pack: `docs/PGBOUNCER_SOAK_PACK_MVP.md` (`test_pgbouncer_soak_b2.py`). Stage 29 T1 TLS ingress pack: `docs/TLS_INGRESS_PACK_MVP.md` (`test_tls_ingress_t1.py`). Stage 29 X1 production cutover pack: `docs/CUTOVER_PACK_MVP.md` (`test_cutover_pack_x1.py`). Stage 29 D1 operator hardening & cutover fidelity: `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) — V1–X1 evidence lock; public API contracts unchanged. Stage 29 H29x exit + freeze: `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`). Stage 30 open (ADR-065): Go-Live Support Fidelity — `docs/STAGE_30_PLAN.md` (`test_stage30_open.py`). Stage 30 L1 evidence ledger: `docs/EVIDENCE_LEDGER_MVP.md` (`test_evidence_ledger_l1.py`). Stage 30 I1 incident pack: `docs/INCIDENT_PACK_MVP.md` (`test_incident_pack_i1.py`). Stage 30 S1 support/Admin fidelity: `docs/SUPPORT_RUNBOOK_MVP.md` (`test_support_runbook_s1.py`). Stage 30 A1 attestation matrix: `docs/ATTESTATION_PACK_MVP.md` (`test_attestation_pack_a1.py`). Stage 30 D1 go-live support fidelity: `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) — L1–A1 evidence lock; public API contracts unchanged. Stage 30 H30x exit + freeze: `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`). Stage 31 open (ADR-067): Commercial MVP Closeout Fidelity — `docs/STAGE_31_PLAN.md` (`test_stage31_open.py`). Stage 31 G1 MVP gate honesty matrix: `docs/MVP_GATE_MATRIX_MVP.md` (`test_mvp_gate_matrix_g1.py`). Stage 31 R1 deferred ADR register: `docs/DEFERRED_ADR_REGISTER_MVP.md` (`test_deferred_adr_register_r1.py`). Stage 31 O1 operator Remaining register: `docs/OPERATOR_REMAINING_MVP.md` (`test_operator_remaining_o1.py`). Stage 31 C1 commercial MVP declaration: `docs/MVP_DECLARATION_MVP.md` (`test_mvp_declaration_c1.py`). Stage 31 D1 closeout fidelity: `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) — G1–C1 evidence lock; public API contracts unchanged. Stage 31 H31x exit + freeze: `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`). Stage 32 open (ADR-069): Commercial MVP Handoff Fidelity — `docs/STAGE_32_PLAN.md` (`test_stage32_open.py`). Stage 32 A1 MVP acceptance archive: `docs/ACCEPTANCE_ARCHIVE_MVP.md` (`test_acceptance_archive_a1.py`). Stage 32 H1 operator handoff: `docs/OPERATOR_HANDOFF_MVP.md` (`test_operator_handoff_h1.py`). Stage 32 N1 commercial release notes: `docs/RELEASE_NOTES_MVP.md` (`test_release_notes_n1.py`). Stage 32 B1 post-MVP backlog: `docs/POST_MVP_BACKLOG_MVP.md` (`test_post_mvp_backlog_b1.py`). Stage 32 D1 handoff fidelity: `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) — A1–B1 evidence lock; public API contracts unchanged. Stage 32 H32x exit + freeze: `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`). Stage 33 open (ADR-071): Commercial MVP Continuity Fidelity — `docs/STAGE_33_PLAN.md` (`test_stage33_open.py`). Stage 33 K1 residual risk register: `docs/RESIDUAL_RISK_MVP.md` (`test_residual_risk_k1.py`). Stage 33 C1 compliance readiness: `docs/COMPLIANCE_READINESS_MVP.md` (`test_compliance_readiness_c1.py`). Stage 33 F1 first-tenant onboarding: `docs/FIRST_TENANT_ONBOARDING_MVP.md` (`test_first_tenant_onboarding_f1.py`). Stage 33 T1 knowledge transfer: `docs/KNOWLEDGE_TRANSFER_MVP.md` (`test_knowledge_transfer_t1.py`). Stage 33 D1 continuity fidelity: `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`). Stage 33 H33x exit + freeze: `docs/STAGE_33_EXIT_CRITERIA.md`, ADR-072 (`test_stage33_exit_h33x.py`). Stage 34 open (ADR-073): Commercial Customer Assurance Fidelity — `docs/STAGE_34_PLAN.md` (`test_stage34_open.py`). Stage 34 A1 assurance evidence: `docs/ASSURANCE_EVIDENCE_MVP.md` (`test_assurance_evidence_a1.py`). Stage 34 C1 compliance questionnaire: `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md` (`test_compliance_questionnaire_c1.py`). Stage 34 D1 assurance fidelity: `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`). Stage 34 H34x exit + freeze: `docs/STAGE_34_EXIT_CRITERIA.md`, ADR-074 (`test_stage34_exit_h34x.py`). Stage 35 open (ADR-075): Commercial End-to-End Operational Smoke Fidelity — `docs/STAGE_35_PLAN.md` (`test_stage35_open.py`). Stage 35 T1 org bootstrap: `docs/E2E_ORG_BOOTSTRAP_MVP.md` (`test_e2e_org_bootstrap_t1.py`). Stage 35 U1 users + RBAC: `docs/E2E_USERS_RBAC_MVP.md` (`test_e2e_users_rbac_u1.py`). Stage 35 P1 purchase-to-stock: `docs/E2E_PURCHASE_STOCK_MVP.md` (`test_e2e_purchase_stock_p1.py`). Stage 35 S1 sale-to-payment: `docs/E2E_SALE_PAYMENT_MVP.md` (`test_e2e_sale_payment_s1.py`). Stage 35 V1 verify financials: `docs/E2E_VERIFY_FINANCIALS_MVP.md` (`test_e2e_verify_financials_v1.py`). Stage 35 R1 backup + restore: `docs/E2E_BACKUP_RESTORE_MVP.md` (`test_e2e_backup_restore_r1.py`). Stage 35 D1 E2E smoke fidelity: `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`). Stage 35 H35x exit + freeze: `docs/STAGE_35_EXIT_CRITERIA.md`, ADR-076 (`test_stage35_exit_h35x.py`). Stage 36 open (ADR-077): Commercial Assurance Completion Fidelity — `docs/STAGE_36_PLAN.md` (`test_stage36_open.py`). Stage 36 S1 support SLA boundary: `docs/SUPPORT_SLA_BOUNDARY_MVP.md` (`test_support_sla_boundary_s1.py`). Stage 36 B1 billing-deferred honesty: `docs/BILLING_DEFERRED_HONESTY_MVP.md` (`test_billing_deferred_honesty_b1.py`). Stage 36 D1 assurance completion fidelity: `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`). Stage 37 open — `docs/STAGE_37_PLAN.md`, ADR-079 (`test_stage37_open.py`). Stage 37 P1 data portability — `docs/DATA_PORTABILITY_MVP.md` (`test_data_portability_p1.py`). Stage 37 E1 erasure honesty — `docs/ERASURE_HONESTY_MVP.md` (`test_erasure_honesty_e1.py`). Stage 37 D1 data protection fidelity — `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`). Stage 37 H37x exit + freeze — `docs/STAGE_37_EXIT_CRITERIA.md`, ADR-080 (`test_stage37_exit_h37x.py`). Stage 38 open — `docs/STAGE_38_PLAN.md`, ADR-081 (`test_stage38_open.py`). Stage 38 V1 vulnerability disclosure — `docs/VULN_DISCLOSURE_MVP.md` (`test_vuln_disclosure_v1.py`). Stage 38 B1 breach notification — `docs/BREACH_NOTIFICATION_MVP.md` (`test_breach_notification_b1.py`). Stage 38 D1 security disclosure fidelity — `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`). Stage 38 H38x exit + freeze — `docs/STAGE_38_EXIT_CRITERIA.md`, ADR-082 (`test_stage38_exit_h38x.py`). Stage 39 open — `docs/STAGE_39_PLAN.md`, ADR-083 (`test_stage39_open.py`). Stage 39 P1 DPA / subprocessor — `docs/DPA_SUBPROCESSOR_MVP.md` (`test_dpa_subprocessor_p1.py`). Stage 39 A1 MSA security addendum — `docs/MSA_ADDENDUM_MVP.md` (`test_msa_addendum_a1.py`). Stage 39 D1 contract evidence fidelity — `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`). Stage 39 H39x Stage 40 open: `docs/STAGE_40_PLAN.md`, ADR-085 (`test_stage40_open.py`). Stage 40 U1: `docs/STATUS_UPTIME_MVP.md` (`test_status_uptime_u1.py`). Stage 40 S1 SBOM/dependency disclosure honesty Complete (MVP) Stage 40 D1 availability & supply-chain fidelity Complete (MVP) Stage 40 exit met — `docs/STAGE_40_EXIT_CRITERIA.md`, ADR-086 (`test_stage40_exit_h40x.py`) Stage 41 open: `docs/STAGE_41_PLAN.md`, ADR-087 (`test_stage41_open.py`). Stage 41 A1 accessibility statement honesty Complete (MVP) Stage 41 C1 change/maintenance governance honesty Complete (MVP) Stage 41 D1 accessibility & change governance fidelity Complete (MVP) Stage 41 exit met — `docs/STAGE_41_EXIT_CRITERIA.md`, ADR-088 (`test_stage41_exit_h41x.py`) Stage 42 open: `docs/STAGE_42_PLAN.md`, ADR-089 (`test_stage42_open.py`). Stage 42 A1 AI use disclosure honesty Complete (MVP) Stage 42 P1 AI model/provider boundary honesty Complete (MVP) Stage 42 D1 AI transparency fidelity Complete (MVP) Stage 42 exit met — `docs/STAGE_42_EXIT_CRITERIA.md`, ADR-090 (`test_stage42_exit_h42x.py`) Stage 43 open: `docs/STAGE_43_PLAN.md`, ADR-091 (`test_stage43_open.py`). Stage 43 T1 ToS / AUP honesty Complete (MVP) — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json` (`test_tos_aup_t1.py`). Stage 43 C1 Cookie / privacy notice honesty Complete (MVP) — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json` (`test_cookie_privacy_notice_c1.py`). Stage 43 D1 commercial legal notice fidelity Complete (MVP) — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`). Stage 43 exit met — `docs/STAGE_43_EXIT_CRITERIA.md`, ADR-092 (`test_stage43_exit_h43x.py`). Stage 44 open: `docs/STAGE_44_PLAN.md`, ADR-093 (`test_stage44_open.py`). Stage 44 R1 data residency / localization honesty Complete (MVP) — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json` (`test_data_residency_r1.py`). Stage 44 E1 encryption / key-management honesty Complete (MVP) — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json` (`test_encryption_kms_e1.py`). Stage 44 D1 commercial data trust fidelity Complete (MVP) — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`). Stage 44 exit met — `docs/STAGE_44_EXIT_CRITERIA.md`, ADR-094 (`test_stage44_exit_h44x.py`). Stage 45 open: `docs/STAGE_45_PLAN.md`, ADR-095 (`test_stage45_open.py`). Stage 45 O1 RTO / RPO recovery objectives honesty Complete (MVP) — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json` (`test_rto_rpo_o1.py`). Stage 45 T1 data retention / return honesty Complete (MVP) — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json` (`test_data_retention_return_t1.py`). Stage 45 D1 commercial continuity & exit fidelity Complete (MVP) — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`). Stage 45 exit met — `docs/STAGE_45_EXIT_CRITERIA.md`, ADR-096 (`test_stage45_exit_h45x.py`). Stage 46 open: `docs/STAGE_46_PLAN.md`, ADR-097 (`test_stage46_open.py`). Stage 46 L1 limitation of liability / indemnity honesty Complete (MVP) — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json` (`test_liability_indemnity_l1.py`). Stage 46 W1 service credit / warranty honesty Complete (MVP) — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json` (`test_service_credit_warranty_w1.py`). Stage 46 D1 commercial liability & remedy fidelity Complete (MVP) — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`). Stage 46 exit met — `docs/STAGE_46_EXIT_CRITERIA.md`, ADR-098 (`test_stage46_exit_h46x.py`). Stage 47 open: `docs/STAGE_47_PLAN.md`, ADR-099 (`test_stage47_open.py`). Stage 47 I1 cyber insurance / COI honesty Complete (MVP) — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json` (`test_cyber_insurance_i1.py`). Stage 47 A1 customer audit rights honesty Complete (MVP) — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json` (`test_customer_audit_rights_a1.py`). Stage 47 D1 commercial insurance & audit fidelity Complete (MVP) — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`). Stage 47 exit met — `docs/STAGE_47_EXIT_CRITERIA.md`, ADR-100 (`test_stage47_exit_h47x.py`). Stage 48 open: `docs/STAGE_48_PLAN.md`, ADR-101 (`test_stage48_open.py`). Stage 48 P1 professional services / SOW honesty Complete (MVP) — `docs/PROFESSIONAL_SERVICES_SOW_MVP.md`, `ops/mvp/professional-services-sow.json` (`test_professional_services_sow_p1.py`). Stage 48 T1 customer training / certification honesty Complete (MVP) — `docs/CUSTOMER_TRAINING_CERT_MVP.md`, `ops/mvp/customer-training-cert.json` (`test_customer_training_cert_t1.py`). Stage 48 D1 commercial services fidelity Complete (MVP) — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`). Stage 48 exit met — `docs/STAGE_48_EXIT_CRITERIA.md`, ADR-102 (`test_stage48_exit_h48x.py`). Stage 49 open: `docs/STAGE_49_PLAN.md`, ADR-103 (`test_stage49_open.py`). Stage 49 R1 partner / reseller terms honesty Complete (MVP) — `docs/PARTNER_RESELLER_MVP.md`, `ops/mvp/partner-reseller.json` (`test_partner_reseller_r1.py`). Stage 49 L1 pricing transparency honesty Complete (MVP) — `docs/PRICING_TRANSPARENCY_MVP.md`, `ops/mvp/pricing-transparency.json`; evidence `/opt/cursor/artifacts/launch/stage49_l1_pricing_transparency.json` (`test_pricing_transparency_l1.py`). Stage 49 D1 commercial channel & pricing fidelity Complete (MVP) — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`). Stage 49 exit met — `docs/STAGE_49_EXIT_CRITERIA.md`, ADR-104 (`test_stage49_exit_h49x.py`). Stage 50 open: `docs/STAGE_50_PLAN.md`, ADR-105 (`test_stage50_open.py`). Stage 50 R1 referral program honesty Complete (MVP) — `docs/REFERRAL_PROGRAM_MVP.md`, `ops/mvp/referral-program.json` (`test_referral_program_r1.py`). Stage 50 F1 freemium trial honesty Complete (MVP) — `docs/FREEMIUM_TRIAL_MVP.md`, `ops/mvp/freemium-trial.json`; evidence `/opt/cursor/artifacts/launch/stage50_f1_freemium_trial.json` (`test_freemium_trial_f1.py`). Stage 50 D1 commercial acquisition & trial fidelity Complete (MVP) — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`). Stage 50 exit met — `docs/STAGE_50_EXIT_CRITERIA.md`, ADR-106 (`test_stage50_exit_h50x.py`). Stage 51 open: `docs/STAGE_51_PLAN.md`, ADR-107 (`test_stage51_open.py`). Stage 51 M1 marketplace presence honesty Complete (MVP) — `docs/MARKETPLACE_PRESENCE_MVP.md`, `ops/mvp/marketplace-presence.json` (`test_marketplace_presence_m1.py`). Stage 51 A1 add-on services honesty Complete (MVP) — `docs/ADDON_SERVICES_MVP.md`, `ops/mvp/addon-services.json`; evidence `/opt/cursor/artifacts/launch/stage51_a1_addon_services.json` (`test_addon_services_a1.py`). Stage 51 D1 commercial marketplace & add-ons fidelity Complete (MVP) — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`). Stage 51 exit met — `docs/STAGE_51_EXIT_CRITERIA.md`, ADR-108 (`test_stage51_exit_h51x.py`). Stage 52 open: `docs/STAGE_52_PLAN.md`, ADR-109 (`test_stage52_open.py`). Stage 52 I1 industry partnerships honesty Complete (MVP) — `docs/INDUSTRY_PARTNERSHIPS_MVP.md`, `ops/mvp/industry-partnerships.json` (`test_industry_partnerships_i1.py`). Stage 52 R1 subscription renewal / annual discount honesty Complete (MVP) — `docs/SUBSCRIPTION_RENEWAL_MVP.md`, `ops/mvp/subscription-renewal.json`; evidence `/opt/cursor/artifacts/launch/stage52_r1_subscription_renewal.json` (`test_subscription_renewal_r1.py`). Stage 52 D1 commercial partnerships & renewal fidelity Complete (MVP) — `docs/STAGE_52_FIDELITY.md` (`test_stage52_fidelity_d1.py`). Stage 52 exit met — `docs/STAGE_52_EXIT_CRITERIA.md`, ADR-110 (`test_stage52_exit_h52x.py`). Stage 53 open: `docs/STAGE_53_PLAN.md`, ADR-111 (`test_stage53_open.py`). Stage 53 A1 API & integration commercial honesty Complete (MVP) — `docs/API_INTEGRATION_COMMERCIAL_MVP.md`, `ops/mvp/api-integration-commercial.json` (`test_api_integration_commercial_a1.py`). Stage 53 C1 cancellation / refund / churn policy honesty Complete (MVP) — `docs/CANCELLATION_CHURN_MVP.md`, `ops/mvp/cancellation-churn.json`; evidence `/opt/cursor/artifacts/launch/stage53_c1_cancellation_churn.json` (`test_cancellation_churn_c1.py`). Stage 53 D1 commercial API & lifecycle fidelity Complete (MVP) — `docs/STAGE_53_FIDELITY.md` (`test_stage53_fidelity_d1.py`). Stage 53 exit met — `docs/STAGE_53_EXIT_CRITERIA.md`, ADR-112 (`test_stage53_exit_h53x.py`). Stage 54 open: `docs/STAGE_54_PLAN.md`, ADR-113 (`test_stage54_open.py`). Stage 54 M1 digital marketing / case studies / testimonials honesty Complete (MVP) — `docs/DIGITAL_MARKETING_MVP.md`, `ops/mvp/digital-marketing.json` (`test_digital_marketing_m1.py`). Stage 54 S1 direct sales honesty Complete (MVP) — `docs/DIRECT_SALES_MVP.md`, `ops/mvp/direct-sales.json`; evidence `/opt/cursor/artifacts/launch/stage54_s1_direct_sales.json` (`test_direct_sales_s1.py`). Stage 54 D1 commercial go-to-market fidelity Complete (MVP) — `docs/STAGE_54_FIDELITY.md` (`test_stage54_fidelity_d1.py`). Stage 54 exit met — `docs/STAGE_54_EXIT_CRITERIA.md`, ADR-114 (`test_stage54_exit_h54x.py`). Stage 55 open: `docs/STAGE_55_PLAN.md`, ADR-115 (`test_stage55_open.py`). Stage 55 W1 white-label licensing commercial honesty Complete (MVP) — `docs/WHITE_LABEL_LICENSING_MVP.md`, `ops/mvp/white-label-licensing.json` (`test_white_label_licensing_w1.py`). Stage 55 U1 unit economics / competitive positioning honesty Complete (MVP) — `docs/UNIT_ECONOMICS_POSITIONING_MVP.md`, `ops/mvp/unit-economics-positioning.json`; evidence `/opt/cursor/artifacts/launch/stage55_u1_unit_economics_positioning.json` (`test_unit_economics_positioning_u1.py`). Stage 55 D1 commercial licensing & positioning fidelity Complete (MVP) — `docs/STAGE_55_FIDELITY.md` (`test_stage55_fidelity_d1.py`). Stage 55 exit met — `docs/STAGE_55_EXIT_CRITERIA.md`, ADR-116 (`test_stage55_exit_h55x.py`). Stage 56 open: `docs/STAGE_56_PLAN.md`, ADR-117 (`test_stage56_open.py`). Stage 56 O1 implementation & onboarding commercial honesty Complete (MVP) — `docs/IMPLEMENTATION_ONBOARDING_MVP.md`, `ops/mvp/implementation-onboarding.json` (`test_implementation_onboarding_o1.py`). Stage 56 G1 geographic expansion honesty Complete (MVP) — `docs/GEOGRAPHIC_EXPANSION_MVP.md`, `ops/mvp/geographic-expansion.json` (`test_geographic_expansion_g1.py`). Stage 56 D1 commercial onboarding & expansion fidelity Complete (MVP) — `docs/STAGE_56_FIDELITY.md` (`test_stage56_fidelity_d1.py`). Stage 56 exit met — `docs/STAGE_56_EXIT_CRITERIA.md`, ADR-118 (`test_stage56_exit_h56x.py`). Stage 57 open: `docs/STAGE_57_PLAN.md`, ADR-119 (`test_stage57_open.py`). Stage 57 A1 mobile app GTM honesty Complete (MVP) — `docs/MOBILE_APP_GTM_MVP.md`, `ops/mvp/mobile-app-gtm.json` (`test_mobile_app_gtm_a1.py`). Stage 57 K1 success metrics honesty Complete (MVP) — `docs/SUCCESS_METRICS_MVP.md`, `ops/mvp/success-metrics.json` (`test_success_metrics_k1.py`). Stage 57 D1 commercial mobile & metrics fidelity Complete (MVP) — `docs/STAGE_57_FIDELITY.md` (`test_stage57_fidelity_d1.py`). Stage 57 exit met — `docs/STAGE_57_EXIT_CRITERIA.md`, ADR-120 (`test_stage57_exit_h57x.py`). Stage 58 open: `docs/STAGE_58_PLAN.md`, ADR-121 (`test_stage58_open.py`). Stage 58 B1 business metrics honesty Complete (MVP) — `docs/BUSINESS_METRICS_MVP.md`, `ops/mvp/business-metrics.json` (`test_business_metrics_b1.py`). Stage 58 I1 AI metrics honesty Complete (MVP) — `docs/AI_METRICS_MVP.md`, `ops/mvp/ai-metrics.json` (`test_ai_metrics_i1.py`). Stage 58 D1 commercial business & AI metrics fidelity Complete (MVP) — `docs/STAGE_58_FIDELITY.md` (`test_stage58_fidelity_d1.py`). Stage 58 exit met — `docs/STAGE_58_EXIT_CRITERIA.md`, ADR-122 (`test_stage58_exit_h58x.py`). Stage 59 open: `docs/STAGE_59_PLAN.md`, ADR-123 (`test_stage59_open.py`). Stage 59 E1 e-commerce integration honesty Complete (MVP) — `docs/ECOMMERCE_INTEGRATION_MVP.md`, `ops/mvp/ecommerce-integration.json` (`test_ecommerce_integration_e1.py`). Stage 59 C1 CRM commercial honesty Complete (MVP) — `docs/CRM_COMMERCIAL_MVP.md`, `ops/mvp/crm-commercial.json` (`test_crm_commercial_c1.py`). Stage 59 D1 commercial channel extensions fidelity Complete (MVP) — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`). Stage 59 exit met — `docs/STAGE_59_EXIT_CRITERIA.md`, ADR-124 (`test_stage59_exit_h59x.py`). Stage 60 open: `docs/STAGE_60_PLAN.md`, ADR-125 (`test_stage60_open.py`). Stage 60 M1 advanced manufacturing honesty Complete (MVP) — `docs/ADVANCED_MANUFACTURING_MVP.md`, `ops/mvp/advanced-manufacturing.json` (`test_advanced_manufacturing_m1.py`). Stage 60 T1 multi-country tax honesty Complete (MVP) — `docs/MULTI_COUNTRY_TAX_MVP.md`, `ops/mvp/multi-country-tax.json` (`test_multi_country_tax_t1.py`). Stage 60 D1 commercial manufacturing & tax fidelity Complete (MVP) — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`). Stage 60 exit met — `docs/STAGE_60_EXIT_CRITERIA.md`, ADR-126 (`test_stage60_exit_h60x.py`). Stage 61 open: `docs/STAGE_61_PLAN.md`, ADR-127 (`test_stage61_open.py`). Stage 61 F1 embedded fintech honesty Complete (MVP) — `docs/EMBEDDED_FINTECH_MVP.md`, `ops/mvp/embedded-fintech.json` (`test_embedded_fintech_f1.py`). Stage 61 S1 supply chain integration honesty Complete (MVP) — `docs/SUPPLY_CHAIN_INTEGRATION_MVP.md`, `ops/mvp/supply-chain-integration.json` (`test_supply_chain_integration_s1.py`). Stage 61 D1 commercial fintech & supply-chain fidelity Complete (MVP) — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`). Stage 61 exit met — `docs/STAGE_61_EXIT_CRITERIA.md`, ADR-128 (`test_stage61_exit_h61x.py`). Stage 62 open: `docs/STAGE_62_PLAN.md`, ADR-129 (`test_stage62_open.py`). Stage 62 I1 IoT integration honesty Complete (MVP) — `docs/IOT_INTEGRATION_MVP.md`, `ops/mvp/iot-integration.json` (`test_iot_integration_i1.py`). Stage 62 A1 AI model marketplace honesty Complete (MVP) — `docs/AI_MODEL_MARKETPLACE_MVP.md`, `ops/mvp/ai-model-marketplace.json` (`test_ai_model_marketplace_a1.py`). Stage 62 D1 commercial IoT & AI marketplace fidelity Complete (MVP) — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`). Stage 62 exit met — `docs/STAGE_62_EXIT_CRITERIA.md`, ADR-130 (`test_stage62_exit_h62x.py`). Stage 63 open: `docs/STAGE_63_PLAN.md`, ADR-131 (`test_stage63_open.py`). Stage 63 P1 IPO readiness honesty Complete (MVP) — `docs/IPO_READINESS_MVP.md`, `ops/mvp/ipo-readiness.json` (`test_ipo_readiness_p1.py`). Stage 63 G1 global scale honesty Complete (MVP) — `docs/GLOBAL_SCALE_MVP.md`, `ops/mvp/global-scale.json` (`test_global_scale_g1.py`). Stage 63 D1 commercial capital & scale fidelity Complete (MVP) — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`). Stage 63 exit met — `docs/STAGE_63_EXIT_CRITERIA.md`, ADR-132 (`test_stage63_exit_h63x.py`). Stage 64 open: `docs/STAGE_64_PLAN.md`, ADR-133 (`test_stage64_open.py`). Stage 64 B1 Advanced BI honesty Complete (MVP) — `docs/ADVANCED_BI_MVP.md`, `ops/mvp/advanced-bi.json` (`test_advanced_bi_b1.py`). Stage 64 F1 Franchise & chain enterprise honesty Complete (MVP) — `docs/FRANCHISE_CHAIN_MVP.md`, `ops/mvp/franchise-chain.json` (`test_franchise_chain_f1.py`). Stage 64 D1 commercial analytics & franchise fidelity Complete (MVP) — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`). Stage 64 exit met — `docs/STAGE_64_EXIT_CRITERIA.md`, ADR-134 (`test_stage64_exit_h64x.py`). Stage 65 open: `docs/STAGE_65_PLAN.md`, ADR-135 (`test_stage65_open.py`). Stage 65 R1 Release pipeline honesty Complete (MVP) — `docs/RELEASE_PIPELINE_MVP.md`, `ops/mvp/release-pipeline.json` (`test_release_pipeline_r1.py`). Stage 65 P1 Controlled business pilot honesty Complete (MVP) — `docs/BUSINESS_PILOT_MVP.md`, `ops/mvp/business-pilot.json` (`test_business_pilot_p1.py`). Stage 65 D1 MVP release-candidate fidelity Complete (MVP) — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`). Stage 65 H65x exit + freeze: `docs/STAGE_65_EXIT_CRITERIA.md`, ADR-136 (`test_stage65_exit_h65x.py`). Stage 66 open: `docs/STAGE_66_PLAN.md`, ADR-138 (`test_stage66_open.py`). Stage 66 L1 Production launch honesty Complete (MVP) — `docs/PRODUCTION_LAUNCH_MVP.md`, `ops/mvp/production-launch.json` (`test_production_launch_l1.py`). Stage 66 T1 First tenant go-live honesty Complete (MVP) — `docs/FIRST_TENANT_GOLIVE_MVP.md`, `ops/mvp/first-tenant-golive.json` (`test_first_tenant_golive_t1.py`). Stage 66 D1 MVP production-launch fidelity Complete (MVP) — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`). Stage 66 H66x exit + freeze: `docs/STAGE_66_EXIT_CRITERIA.md`, ADR-139 (`test_stage66_exit_h66x.py`). Stage 67 open: `docs/STAGE_67_PLAN.md`, ADR-140 (`test_stage67_open.py`). Stage 67 H1 Production hypercare honesty Complete (MVP) — `docs/PRODUCTION_HYPERCARE_MVP.md`, `ops/mvp/production-hypercare.json` (`test_production_hypercare_h1.py`). Stage 67 C1 Post-launch continuity honesty Complete (MVP) — `docs/POST_LAUNCH_CONTINUITY_MVP.md`, `ops/mvp/post-launch-continuity.json` (`test_post_launch_continuity_c1.py`). Stage 67 D1 MVP post-launch continuity fidelity Complete (MVP) — `docs/STAGE_67_FIDELITY.md` (`test_stage67_fidelity_d1.py`). Stage 67 H67x exit + freeze: `docs/STAGE_67_EXIT_CRITERIA.md`, ADR-141 (`test_stage67_exit_h67x.py`). Stage 68 open: `docs/STAGE_68_PLAN.md`, ADR-142 (`test_stage68_open.py`). Stage 68 H1 Ribdigi House console honesty Complete (MVP) — `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json` (`test_ribdigi_house_console_h1.py`). Stage 68 T1 Tenant Company console honesty Complete (MVP) — `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json` (`test_tenant_company_console_t1.py`). Stage 68 D1 Platform ↔ Tenant console fidelity Complete (MVP) — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`). Stage 68 H68x exit + freeze: `docs/STAGE_68_EXIT_CRITERIA.md`, ADR-143 (`test_stage68_exit_h68x.py`). Stage 69 open: `docs/STAGE_69_PLAN.md`, ADR-144 (`test_stage69_open.py`). Stage 69 V1 Pre-flight verification honesty Complete (MVP) — `docs/PREFLIGHT_VERIFICATION_MVP.md`, `ops/mvp/preflight-verification.json` (`test_preflight_verification_v1.py`). Stage 69 A1 Go-live attestation honesty Complete (MVP) — `docs/GOLIVE_ATTESTATION_MVP.md`, `ops/mvp/golive-attestation.json` (`test_golive_attestation_a1.py`). Honesty: `section_7_signed` / `attestation_claimed` / `go_live_claimed` remain false (packaging ≠ §7 signed). Stage 69 D1 Commercial Go-Live fidelity Complete (MVP) — `docs/STAGE_69_FIDELITY.md` (`test_stage69_fidelity_d1.py`); maps V1–A1. Stage 69 H69x exit + freeze Complete (MVP) — `docs/STAGE_69_EXIT_CRITERIA.md`, ADR-145 (`test_stage69_exit_h69x.py`). Stage 70 open: `docs/STAGE_70_PLAN.md`, ADR-146 (`test_stage70_open.py`). Stage 70 F1 First commercial day ops honesty Complete (MVP) — `docs/FIRST_COMMERCIAL_DAY_MVP.md`, `ops/mvp/first-commercial-day.json` (`test_first_commercial_day_f1.py`). Honesty: `first_commercial_day_claimed` / `commercial_day_ops_live_claimed` remain false (packaging ≠ first-day live). Stage 70 G1 Commercial go-live closeout honesty Complete (MVP) — `docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md`, `ops/mvp/commercial-golive-closeout.json` (`test_commercial_golive_closeout_g1.py`). Honesty: `go_live_claimed` / `commercial_golive_closeout_claimed` remain false (packaging ≠ go-live). Stage 70 D1 First Commercial Day fidelity Complete (MVP) — `docs/STAGE_70_FIDELITY.md` (`test_stage70_fidelity_d1.py`); maps F1–G1. Stage 70 H70x exit + freeze Complete (MVP) — `docs/STAGE_70_EXIT_CRITERIA.md`, ADR-147 (`test_stage70_exit_h70x.py`). Stage 71 open: `docs/STAGE_71_PLAN.md`, ADR-148 (`test_stage71_open.py`). Stage 71 S1 Steady-state commercial ops honesty Complete (MVP) — `docs/STEADY_STATE_OPS_MVP.md`, `ops/mvp/steady-state-ops.json` (`test_steady_state_ops_s1.py`). Honesty: `steady_state_ops_claimed` / `commercial_acceptance_claimed` remain false (packaging ≠ steady-state live). Stage 71 A1 Commercial acceptance gate honesty Complete (MVP) — `docs/COMMERCIAL_ACCEPTANCE_MVP.md`, `ops/mvp/commercial-acceptance.json` (`test_commercial_acceptance_a1.py`). Honesty: `commercial_acceptance_claimed` / `go_live_claimed` remain false (packaging ≠ acceptance Complete). Stage 71 D1 Commercial Steady-State fidelity Complete (MVP) — `docs/STAGE_71_FIDELITY.md` (`test_stage71_fidelity_d1.py`); maps S1–A1. Stage 71 H71x exit + freeze Complete (MVP) — `docs/STAGE_71_EXIT_CRITERIA.md`, ADR-149 (`test_stage71_exit_h71x.py`). Stage 72 open: `docs/STAGE_72_PLAN.md`, ADR-150 (`test_stage72_open.py`). Stage 72 R1 Commercial residual remaining honesty Complete (MVP) — `docs/COMMERCIAL_RESIDUAL_MVP.md`, `ops/mvp/commercial-residual.json` (`test_commercial_residual_r1.py`). Stage 72 P1 Commercial packaging archive honesty Complete (MVP) — `docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md`, `ops/mvp/commercial-packaging-archive.json` (`test_commercial_packaging_archive_p1.py`). Stage 72 D1 Commercial Packaging Closeout fidelity Complete (MVP) — `docs/STAGE_72_FIDELITY.md` (`test_stage72_fidelity_d1.py`); maps R1–P1. Stage 72 H72x exit + freeze Complete (MVP) — `docs/STAGE_72_EXIT_CRITERIA.md`, ADR-151 (`test_stage72_exit_h72x.py`). Stage 73 open: `docs/STAGE_73_PLAN.md`, ADR-152 (`test_stage73_open.py`). Stage 73 E1 Commercial evidence chain honesty Complete (MVP) — `docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md`, `ops/mvp/commercial-evidence-chain.json` (`test_commercial_evidence_chain_e1.py`). Stage 73 A1 Commercial assurance boundary honesty Complete (MVP) — `docs/COMMERCIAL_ASSURANCE_MVP.md`, `ops/mvp/commercial-assurance.json` (`test_commercial_assurance_a1.py`). Stage 73 D1 Commercial Assurance fidelity Complete (MVP) — `docs/STAGE_73_FIDELITY.md` (`test_stage73_fidelity_d1.py`); maps E1–A1. Stage 73 H73x exit + freeze Complete (MVP) — `docs/STAGE_73_EXIT_CRITERIA.md`, ADR-153 (`test_stage73_exit_h73x.py`). Stage 74 open: `docs/STAGE_74_PLAN.md`, ADR-154 (`test_stage74_open.py`). Stage 74 S1 Commercial support boundary honesty Complete (MVP) — `docs/COMMERCIAL_SUPPORT_MVP.md`, `ops/mvp/commercial-support.json` (`test_commercial_support_s1.py`). Stage 74 U1 Commercial status boundary honesty Complete (MVP) — `docs/COMMERCIAL_STATUS_MVP.md`, `ops/mvp/commercial-status.json` (`test_commercial_status_u1.py`). Stage 74 D1 Commercial Operator Boundary fidelity Complete (MVP) — `docs/STAGE_74_FIDELITY.md` (`test_stage74_fidelity_d1.py`); maps S1–U1. Stage 74 H74x exit + freeze Complete (MVP) — `docs/STAGE_74_EXIT_CRITERIA.md`, ADR-155 (`test_stage74_exit_h74x.py`). Stage 75 C1 commercial security contact honesty Complete (MVP) — `docs/COMMERCIAL_SECURITY_CONTACT_MVP.md`, `ops/mvp/commercial-security-contact.json` (`test_commercial_security_contact_c1.py`); security contact live Remaining. Stage 75 P1 commercial privacy notice honesty Complete (MVP) — `docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md`, `ops/mvp/commercial-privacy-notice.json` (`test_commercial_privacy_notice_p1.py`); privacy notice live Remaining. Stage 75 D1 Commercial Trust Boundary fidelity Complete (MVP) — `docs/STAGE_75_FIDELITY.md` (`test_stage75_fidelity_d1.py`); maps C1–P1. Stage 75 H75x exit + freeze Complete (MVP) — `docs/STAGE_75_EXIT_CRITERIA.md`, ADR-157 (`test_stage75_exit_h75x.py`). Stage 76 T1 commercial terms honesty Complete (MVP) — `docs/COMMERCIAL_TERMS_MVP.md`, `ops/mvp/commercial-terms.json` (`test_commercial_terms_t1.py`); signed ToS Remaining. Stage 76 B1 commercial billing deferred honesty Complete (MVP) — `docs/COMMERCIAL_BILLING_DEFERRED_MVP.md`, `ops/mvp/commercial-billing-deferred.json` (`test_commercial_billing_deferred_b1.py`); paid billing Remaining. Stage 76 D1 Commercial Contract Boundary fidelity Complete (MVP) — `docs/STAGE_76_FIDELITY.md` (`test_stage76_fidelity_d1.py`); maps T1–B1. Stage 76 H76x exit + freeze Complete (MVP) — `docs/STAGE_76_EXIT_CRITERIA.md`, ADR-159 (`test_stage76_exit_h76x.py`). Stage 77 A1 commercial DPA honesty Complete (MVP) — `docs/COMMERCIAL_DPA_MVP.md`, `ops/mvp/commercial-dpa.json` (`test_commercial_dpa_a1.py`); signed DPA Remaining. Stage 77 L1 commercial liability honesty Complete (MVP) — `docs/COMMERCIAL_LIABILITY_MVP.md`, `ops/mvp/commercial-liability.json` (`test_commercial_liability_l1.py`); liability cap signed Remaining. Stage 77 D1 Commercial Legal Envelope fidelity Complete (MVP) — `docs/STAGE_77_FIDELITY.md` (`test_stage77_fidelity_d1.py`); maps A1–L1. Stage 77 H77x exit + freeze Complete (MVP) — `docs/STAGE_77_EXIT_CRITERIA.md`, ADR-161 (`test_stage77_exit_h77x.py`). Stage 78 P1 commercial pricing honesty Complete (MVP) — `docs/COMMERCIAL_PRICING_MVP.md`, `ops/mvp/commercial-pricing.json` (`test_commercial_pricing_p1.py`); public pricing portal Remaining. Stage 78 S1 commercial professional services honesty Complete (MVP) — `docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md`, `ops/mvp/commercial-professional-services.json` (`test_commercial_professional_services_s1.py`); signed SOW Remaining. Stage 78 D1 Commercial Procurement Boundary fidelity Complete (MVP) — `docs/STAGE_78_FIDELITY.md` (`test_stage78_fidelity_d1.py`); maps P1–S1. Stage 78 H78x exit + freeze Complete (MVP) — `docs/STAGE_78_EXIT_CRITERIA.md`, ADR-163 (`test_stage78_exit_h78x.py`). Stage 79 R1 commercial data retention honesty Complete (MVP) — `docs/COMMERCIAL_DATA_RETENTION_MVP.md`, `ops/mvp/commercial-data-retention.json` (`test_commercial_data_retention_r1.py`); data return portal Remaining. Stage 79 A1 commercial customer audit honesty Complete (MVP) — `docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md`, `ops/mvp/commercial-customer-audit.json` (`test_commercial_customer_audit_a1.py`); customer audit rights live Remaining. Stage 79 D1 Commercial Data Exit fidelity Complete (MVP) — `docs/STAGE_79_FIDELITY.md` (`test_stage79_fidelity_d1.py`); maps R1–A1. Stage 79 H79x exit + freeze Complete (MVP) — `docs/STAGE_79_EXIT_CRITERIA.md`, ADR-165 (`test_stage79_exit_h79x.py`). Stage 80 open Complete (MVP) — `docs/ADR_166_STAGE80_OPEN.md`, `docs/STAGE_80_PLAN.md` (`test_stage80_open.py`). Stage 80 P1 platform dashboard charts Complete (MVP) — `/api/v1/platform/dashboard/*` (`test_platform_dashboard_charts_p1.py`); `mrr_fabricated_claimed: false` (ADR-002). Stage 80 T1 tenant role-scoped dashboards Complete (MVP) — `dashboard_views` (`test_tenant_role_dashboard_t1.py`). Stage 80 D1 Dual-Console Dashboard fidelity Complete (MVP) — `docs/STAGE_80_FIDELITY.md` (`test_stage80_fidelity_d1.py`); maps P1–T1. Stage 80 H80x exit + freeze Complete (MVP) — `docs/STAGE_80_EXIT_CRITERIA.md`, ADR-167 (`test_stage80_exit_h80x.py`). Stage 81 open Complete (MVP) — `docs/ADR_168_STAGE81_OPEN.md`, `docs/STAGE_81_PLAN.md` (`test_stage81_open.py`). Stage 81 A1 Tenant Admin RBAC console surfaces Complete (MVP) — `/users`, `/admin/roles`, `/admin/permissions` (`test_admin_console_a1.py`). Stage 81 S1 store-scoped manager ops Complete (MVP) — `store_scope` / `stores.manager_id` (`test_store_scoped_manager_s1.py`); `user_store_membership_claimed: false` (ADR-005). Stage 81 D1 Dual-Console Admin fidelity Complete (MVP) — `docs/STAGE_81_FIDELITY.md` (`test_stage81_fidelity_d1.py`); maps A1–S1. Stage 81 H81x exit + freeze Complete (MVP) — `docs/STAGE_81_EXIT_CRITERIA.md`, ADR-169 (`test_stage81_exit_h81x.py`). Stage 82 open Complete (MVP) — `docs/ADR_170_STAGE82_OPEN.md`, `docs/STAGE_82_PLAN.md` (`test_stage82_open.py`). Stage 82 C1 tenant dashboard slices Complete (MVP) — `/api/v1/dashboard/summary|sales-trend|top-products|expenses|stock-alerts|user-stats` (`test_dashboard_slices_c1.py`). Stage 82 P1 Platform Plans console Complete (MVP) — `/platform/plans` + Activity alias (`test_platform_plans_p1.py`); `mrr_fabricated_claimed: false` (ADR-002). Stage 82 D1 Dual-Console Surface Parity fidelity Complete (MVP) — `docs/STAGE_82_FIDELITY.md` (`test_stage82_fidelity_d1.py`); maps C1–P1. Stage 82 H82x exit + freeze Complete (MVP) — `docs/STAGE_82_EXIT_CRITERIA.md`, ADR-171 (`test_stage82_exit_h82x.py`). Stage 83 open Complete (MVP) — `docs/ADR_172_STAGE83_OPEN.md`, `docs/STAGE_83_PLAN.md` (`test_stage83_open.py`). Stage 83 S1 store-scoped chart depth Complete (MVP) — `store_ids` on charts/slices (`test_store_scoped_charts_s1.py`). Stage 83 U1 Tenant Admin user-ops Complete (MVP) — reset password + org assignment UI (`test_admin_user_ops_u1.py`). Stage 83 D1 Dual-Console Ops fidelity Complete (MVP) — `docs/STAGE_83_FIDELITY.md` (`test_stage83_fidelity_d1.py`); maps S1–U1. Stage 83 H83x exit + freeze Complete (MVP) — `docs/STAGE_83_EXIT_CRITERIA.md`, ADR-173 (`test_stage83_exit_h83x.py`). Stage 84 A1 dotted permission aliases Complete (MVP) — `view`→`read`; `inventory.view` / `inventory:read` (`test_permission_aliases_a1.py`). Stage 84 S1 dashboard slice depth Complete (MVP) — expenses-by-category + `/dashboard/credit` + cashier open-shift UI (`test_dashboard_slice_depth_s1.py`). Stage 84 D1 Dual-Console Permission & Slice fidelity Complete (MVP) — `docs/STAGE_84_FIDELITY.md` (`test_stage84_fidelity_d1.py`). Stage 84 H84x exit + freeze Complete (MVP) — `docs/STAGE_84_EXIT_CRITERIA.md`, ADR-175 (`test_stage84_exit_h84x.py`). Stage 85 R1 platform subscriptions roster Complete (MVP) — tenant×plan metadata (`test_platform_subscriptions_r1.py`); `subscriptions_live_claimed` remains false. Stage 85 E1 admin email password reset Complete (MVP) — `POST /users/{id}/password-reset-email` (`test_admin_email_reset_e1.py`). Stage 85 L1 org-chart role catalog Complete (MVP) — Manager/Tenant Admin labels + system matrix (`test_org_role_catalog_l1.py`). Stage 85 D1 House Roster & Tenant Access Ops fidelity Complete (MVP) — `docs/STAGE_85_FIDELITY.md` (`test_stage85_fidelity_d1.py`). Stage 85 H85x exit + freeze Complete (MVP) — `docs/STAGE_85_EXIT_CRITERIA.md`, ADR-177 (`test_stage85_exit_h85x.py`). Stage 86 P1 House tenant provision Complete (MVP) — `POST /platform/tenants` (`test_platform_tenant_provision_p1.py`). Stage 86 E1 platform email password reset Complete (MVP) — `POST /platform/users/{id}/password-reset-email` (`test_platform_email_reset_e1.py`). Stage 86 A1 platform audit Activity depth Complete (MVP) — filters + `/platform/activity` (`test_platform_audit_activity_a1.py`). Stage 86 D1 House Provision & Platform Access Ops fidelity Complete (MVP) — `docs/STAGE_86_FIDELITY.md` (`test_stage86_fidelity_d1.py`). Stage 86 H86x exit + freeze Complete (MVP) — `docs/STAGE_86_EXIT_CRITERIA.md`, ADR-179 (`test_stage86_exit_h86x.py`). Stage 87 X1 platform audit export + chain verify Complete (MVP) — `GET /platform/audit/export` / `GET /platform/audit/verify` (`test_platform_audit_integrity_x1.py`). Stage 87 Y1 House ops surface polish Complete (MVP) — health cards, last_activity UI, `PATCH /platform/tenants/{id}/notes`, settings honesty (`test_house_ops_surface_y1.py`). Stage 87 Z1 console boundary hardening Complete (MVP) — `ribdigi_principal` cookie + middleware + soft-delete honesty (`test_console_boundary_z1.py`). Stage 87 D1 House Integrity & Console Boundary Ops fidelity Complete (MVP) — `docs/STAGE_87_FIDELITY.md` (`test_stage87_fidelity_d1.py`). Stage 87 H87x exit + freeze Complete (MVP) — `docs/STAGE_87_EXIT_CRITERIA.md`, ADR-181 (`test_stage87_exit_h87x.py`). Stage 88 L1 tenant lifecycle controls Complete (MVP) — `PATCH /platform/tenants/{id}/lifecycle` + suspend reason (`test_platform_tenant_lifecycle_l1.py`). Stage 88 R1 tenant roster export + at-risk queue Complete (MVP) — `GET /platform/tenants/export` / `GET /platform/tenants/at-risk` (`test_platform_tenant_roster_r1.py`). Stage 88 S1 platform staff invite + session ops Complete (MVP) — email invite + `GET/DELETE /platform/users/sessions` (`test_platform_staff_security_s1.py`). Stage 88 D1 House Lifecycle & Staff Security Ops fidelity Complete (MVP) — `docs/STAGE_88_FIDELITY.md` (`test_stage88_fidelity_d1.py`). Stage 88 H88x exit + freeze Complete (MVP) — `docs/STAGE_88_EXIT_CRITERIA.md`, ADR-183 (`test_stage88_exit_h88x.py`). Stage 89 A1 House Tenant Admin assist Complete (MVP) — `POST /platform/tenants/{id}/admin/password-reset-email` / `…/admin/resend-verification` (`test_platform_tenant_admin_assist_a1.py`). Stage 89 F1 roster filters + dashboard at-risk KPIs Complete (MVP) — `plan_code`/`industry` filters + `at_risk_count` (`test_platform_roster_intel_f1.py`). Stage 89 C1 plan catalog + billing roster depth Complete (MVP) — metadata catalog + trial_ends deep-links (`test_platform_catalog_billing_c1.py`). Stage 89 D1 House Customer Assist & Roster Intelligence Ops fidelity Complete (MVP) — `docs/STAGE_89_FIDELITY.md` (`test_stage89_fidelity_d1.py`). Stage 89 H89x exit + freeze Complete (MVP) — `docs/STAGE_89_EXIT_CRITERIA.md`, ADR-185 (`test_stage89_exit_h89x.py`). Stage 90 E1 House email delivery visibility Complete (MVP) — `platform.email.delivery` audit + `delivery_only` (`test_platform_email_delivery_visibility_e1.py`). Stage 90 O1 operator surfaces Complete (MVP) — Health contacts/security + Settings runbook links (`test_house_operator_surfaces_o1.py`). Stage 90 Q1 roster findability + plan context Complete (MVP) — admin email search + detail soft limits (`test_platform_roster_findability_q1.py`). Stage 90 D1 House Operator Visibility & Delivery Ops fidelity Complete (MVP) — `docs/STAGE_90_FIDELITY.md` (`test_stage90_fidelity_d1.py`). Stage 90 H90x exit + freeze Complete (MVP) — `docs/STAGE_90_EXIT_CRITERIA.md`, ADR-187 (`test_stage90_exit_h90x.py`). Stage 91 I1 Audit/Activity date-range investigation Complete (MVP) — `test_platform_audit_investigation_i1.py`. Stage 91 N1 dashboard→roster deep-links + tenant last House email delivery Complete (MVP) — `test_platform_nav_delivery_n1.py`. Stage 91 P1 staff presence / health required / House TZ / `GET /platform/evidence` Complete (MVP) — `test_house_posture_evidence_p1.py`. Stage 91 D1 House Operator Investigation & Evidence Ops fidelity Complete (MVP) — `docs/STAGE_91_FIDELITY.md` (`test_stage91_fidelity_d1.py`). Stage 91 H91x exit + freeze Complete (MVP) — `docs/STAGE_91_EXIT_CRITERIA.md`, ADR-189 (`test_stage91_exit_h91x.py`). Stage 92 B1 Investigation export + evidence download Complete (MVP) — `test_stage92_console_workflow_b1.py`. Stage 92 G1 roster triage + commercial-metadata context Complete (MVP) — `test_stage92_roster_context_g1.py`. Stage 92 K1 House regional formats + runtime evidence detail Complete (MVP) — `test_stage92_readiness_formats_k1.py`. Stage 92 D1 House Console Workflow & Readiness Ops fidelity Complete (MVP) — `docs/STAGE_92_FIDELITY.md` (`test_stage92_fidelity_d1.py`). Stage 92 H92x exit + freeze Complete (MVP) — `docs/STAGE_92_EXIT_CRITERIA.md`, ADR-191 (`test_stage92_exit_h92x.py`). Stage 93 M1 Roster navigation & export Complete (MVP) — `test_stage93_roster_navigation_m1.py`. Stage 93 J1 Staff delivery & integrity Complete (MVP) — `test_stage93_staff_integrity_j1.py`. Stage 93 V1 Format, evidence & runtime posture Complete (MVP) — `test_stage93_runtime_posture_v1.py`. Stage 93 D1 House Navigation & Runtime Ops fidelity Complete (MVP) — `docs/STAGE_93_FIDELITY.md` (`test_stage93_fidelity_d1.py`). Stage 93 H93x exit + freeze Complete (MVP) — `docs/STAGE_93_EXIT_CRITERIA.md`, ADR-193 (`test_stage93_exit_h93x.py`). Stage 94 open Complete (MVP) — `docs/STAGE_94_PLAN.md`, ADR-194 (`test_stage94_open.py`). Stage 94 W1 Platform staff discovery Complete (MVP) — `test_stage94_staff_discovery_w1.py`. Stage 94 H1 Configuration integrity & release identity Complete (MVP) — `test_stage94_configuration_integrity_h1.py` (`runtime_identity`). Stage 94 T2 Console state & queue awareness Complete (MVP) — `test_stage94_console_state_t2.py`. Stage 94 D1 House Discovery & Runtime Assurance Ops fidelity Complete (MVP) — `docs/STAGE_94_FIDELITY.md` (`test_stage94_fidelity_d1.py`). Stage 94 H94x exit + freeze Complete (MVP) — `docs/STAGE_94_EXIT_CRITERIA.md`, ADR-195 (`test_stage94_exit_h94x.py`). Stage 95 open Complete (MVP) — `docs/STAGE_95_PLAN.md`, ADR-196 (`test_stage95_open.py`). Stage 95 N1 Tenant Shell IA regrouping Complete (MVP) — `test_stage95_shell_ia_n1.py`. Stage 95 P1 Party & stock discoverability Complete (MVP) — `test_stage95_party_stock_p1.py`. Stage 95 C1 Chrome & settings alias fidelity Complete (MVP) — `test_stage95_chrome_c1.py`. Stage 95 D1 Tenant MVP Navigation Ops fidelity Complete (MVP) — `docs/STAGE_95_FIDELITY.md` (`test_stage95_fidelity_d1.py`). Stage 95 H95x exit + freeze Complete (MVP) — `docs/STAGE_95_EXIT_CRITERIA.md`, ADR-197 (`test_stage95_exit_h95x.py`). Stage 96 open Complete (MVP) — `docs/STAGE_96_PLAN.md`, ADR-198 (`test_stage96_open.py`). Stage 96 B1 Dashboard Business Overview fidelity Complete (MVP) — `test_stage96_dashboard_overview_b1.py`. Stage 96 G1 Global topbar search Complete (MVP) — `test_stage96_global_search_g1.py` (`GET /search`). Stage 96 L1 Finance / Sales / Settings leaf fidelity Complete (MVP) — `test_stage96_leaf_fidelity_l1.py`. Stage 96 D1 Tenant MVP Outline Surface Fidelity Ops fidelity Complete (MVP) — `docs/STAGE_96_FIDELITY.md` (`test_stage96_fidelity_d1.py`). Stage 96 H96x exit + freeze Complete (MVP) — `docs/STAGE_96_EXIT_CRITERIA.md`, ADR-199 (`test_stage96_exit_h96x.py`).  Stages 1–42 frozen for Stage 42 scope; external LLM / AI certification Remaining. — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`); maps A1–P1; `ai_certification_claimed` / `external_llm_claimed` remain false; external LLM / AI certification Remaining. — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining. — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining.; Stages 1–41 frozen for Stage 41 scope; WCAG AA audit / public change calendar Remaining. — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`); maps A1–C1; `wcag_aa_claimed` / `change_calendar_live` remain false; WCAG AA audit / public change calendar Remaining. — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json` (`test_change_governance_c1.py`); public change calendar Remaining. — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining.; Stages 1–40 frozen for Stage 40 scope; live status page / SBOM pipeline Remaining. — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`); maps U1–S1; `status_page_live` / `sbom_pipeline_live` remain false; live status page / SBOM pipeline Remaining. — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining. exit + freeze — `docs/STAGE_39_EXIT_CRITERIA.md`, ADR-084 (`test_stage39_exit_h39x.py`). Stage 36 H36x exit + freeze: `docs/STAGE_36_EXIT_CRITERIA.md`, ADR-078 (`test_stage36_exit_h36x.py`).

### 1.1 Request Format
- All requests and responses use **JSON**.
- Content-Type header must be: `application/json`
- Date format: **ISO 8601** (`YYYY-MM-DDTHH:MM:SSZ`)
- Currency values are sent as **decimal strings** or numbers; prefer decimal strings for money fields where schemas require them.

### 1.2 Response Envelope
Successful handlers return the `env()` envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

HTTP errors typically use FastAPI’s `{"detail": "..."}` (string) or structured `{"detail": {"code": "...", "message": "..."}}` for gated auth cases. Rate-limit `429` responses use an envelope with `success: false`, `detail: "RATE_LIMIT_EXCEEDED"`, and `Retry-After` / `X-RateLimit-*` headers. Correlation for ops logs uses `X-Request-ID` (Stage 18 L1) — not a field inside `env()`.

### 1.3 Pagination
Most catalog/party list endpoints return the full array in `data` (MVP-sized tenants). High-volume / filtered lists support an optional **`limit`** query parameter (examples: `GET /audit-logs?limit=200`, AI history, some reports). Cursor/`page` pagination is **deferred** post-MVP.

### 1.4 Versioning & OpenAPI
- All routes are mounted under **`/api/v1`**.
- OpenAPI is auto-generated by FastAPI: `GET /openapi.json`, interactive `GET /docs` / `GET /redoc` when `APP_ENV` is not `production` (disabled in production — Stage 5 S1).
- Webhooks: HMAC-signed outbound subscriptions under `/api/v1/webhooks` (Stage 6 W1; Stage 19 A1 regression).

---

### 1.5 HTTP Methods
| Method | Usage |
|--------|-------|
| `GET` | Retrieve resources |
| `POST` | Create resources |
| `PUT` | Full update (rarely used; prefer PATCH) |
| `PATCH` | Partial update |
| `DELETE` | Soft-delete / remove resources where supported |

---

## 2. Authentication

RIBDIGI ERP uses **JWT (JSON Web Tokens)** with password-grant login (OAuth2 resource-owner style). Stage 19 K1 proves `POST /auth/login`, `POST /auth/refresh` (rotation), API keys, and rate-limit headers (`test_auth_api_fidelity_k1.py`).

### 2.1 Login
**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "email": "admin@company.com",
  "password": "SecurePass123!",
  "tenant_id": "tenant_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "usr_001",
      "email": "admin@company.com",
      "role": "company_admin",
      "tenant_id": "tenant_abc123"
    }
  }
}
```

### 2.2 Refresh Token
**Endpoint:** `POST /auth/refresh`

Rotates the session: validates the refresh token hash against `auth_sessions`, revokes the old session, and issues a new access + refresh pair. Reusing the old refresh token returns `401`. (Stage 19 K1)

**Request:**
```json
{
  "refresh_token": "…"
}
```

### 2.3 Logout
**Endpoint:** `POST /auth/logout`

**Headers:** `Authorization: Bearer <access_token>`

### 2.4 Password Reset
**Endpoint:** `POST /auth/password-reset-request`

**Request:**
```json
{
  "email": "admin@company.com"
}
```

**Endpoint:** `POST /auth/password-reset`

**Request:**
```json
{
  "token": "reset_token_from_email",
  "new_password": "NewSecurePass456!"
}
```

### 2.5 Two-Factor Authentication (Optional)
**Endpoint:** `POST /auth/2fa/enable`

**Endpoint:** `POST /auth/2fa/verify`

**Request:**
```json
{
  "code": "123456"
}
```

### 2.6 Session Management
**Endpoint:** `GET /auth/sessions`

**Endpoint:** `DELETE /auth/sessions/{session_id}`

### 2.7 API Keys (Stage 6 K1 / Stage 7 K2 / BR-18.1)
Tenant admins manage integration keys. The raw secret is returned **once** on create.

| Method | Endpoint | Notes |
|--------|----------|-------|
| `GET` | `/api-keys` | List keys (prefix + metadata; no secret). Includes `request_count`, `last_used_at`. |
| `POST` | `/api-keys` | Create (`name`, optional `permissions`, `expires_at`) |
| `GET` | `/api-keys/{id}` | Get metadata |
| `GET` | `/api-keys/{id}/usage` | Stage 7 K2 — usage stats (`days` query, default 30, max 90): `total_requests`, `period_requests`, zero-filled `series[{date,requests}]` |
| `DELETE` | `/api-keys/{id}` | Revoke |

**Authenticate requests** with either:
- Header `X-API-Key: rdk_…`
- Header `Authorization: Bearer rdk_…`

Optional `X-Tenant-ID` must match the key’s tenant when present. Permissions are a module→actions map (defaults: inventory/sales/purchasing/customers/reports `read`). Each successful authentication increments lifetime and daily request counters (stored in `api_key_usage_daily`).

---

## 3. Tenant Management

### 3.1 Register Company (Tenant)
**Endpoint:** `POST /tenants`

**Request:**
```json
{
  "company_name": "Acme Retail Ltd",
  "industry": "retail",
  "currency": "USD",
  "timezone": "America/New_York",
  "fiscal_year_start": "2026-01-01",
  "admin_email": "admin@acme.com",
  "admin_password": "SecurePass123!",
  "subscription_plan": "trial"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "tenant_id": "tenant_abc123",
    "company_name": "Acme Retail Ltd",
    "status": "trial",
    "api_key": "rk_live_...",
    "created_at": "2026-08-07T13:51:00Z"
  }
}
```

### 3.2 Get Tenant Profile
**Endpoint:** `GET /tenants/{tenant_id}`

**Current tenant (Stage 21 T1/C1):** `GET /tenants/me` / `PATCH /tenants/me` — company admin / super_admin profile (legal name, registration/tax IDs, billing/shipping/warehouse addresses, contact person, currency, logo via `/tenants/me/logo`). `document_numbering` + `document_numbering_preview` cover sales/purchase series including order, return, credit note, debit note (Stage 24 N1: `test_document_numbering_n1.py`). Evidence: `test_tenant_lifecycle_t1.py`, `test_company_currency_tax_c1.py`.

### 3.3 Update Tenant Profile
**Endpoint:** `PATCH /tenants/{tenant_id}`

**Request:**
```json
{
  "company_name": "Acme Retail Ltd",
  "logo_url": "https://cdn.ribdigi.com/logos/acme.png",
  "settings": {
    "currency": "USD",
    "timezone": "America/New_York",
    "date_format": "MM/DD/YYYY",
    "number_format": "#,##0.00"
  }
}
```

### 3.4 Tenant Status Management
**Endpoint:** `PATCH /tenants/{tenant_id}/status`

**Request:**
```json
{
  "status": "active"
}
```

**Allowed statuses:** `trial`, `active`, `suspended`

### 3.4a Onboarding Checklist (Stage 6 N2)

Authenticated users can read progress; `company_admin` / `super_admin` may skip steps or dismiss the banner (≥80% progress).

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/onboarding/checklist` | Auto-detected steps + progress |
| `POST` | `/onboarding/checklist/steps/{step_id}/skip` | Admin |
| `POST` | `/onboarding/checklist/steps/{step_id}/unskip` | Admin |
| `POST` | `/onboarding/checklist/dismiss` | Admin; requires ≥80% |
| `POST` | `/onboarding/checklist/restore` | Admin |

Steps: `setup_company`, `add_products`, `create_supplier`, `stock_ready`, `first_sale`.

### 3.5 Company Setup
**Endpoint:** `POST /tenants/{tenant_id}/setup`

**Request:**
```json
{
  "branches": [
    {
      "name": "Main Branch",
      "address": "123 Main St",
      "phone": "+1-555-0100"
    }
  ],
  "warehouses": [
    {
      "name": "Central Warehouse",
      "location": "Warehouse District"
    }
  ],
  "departments": ["Sales", "Inventory", "Accounting"],
  "tax_config": {
    "vat_enabled": true,
    "default_tax_rate": 10.0
  }
}
```

---

## 4. User Management

### 4.1 Create User
**Endpoint:** `POST /users`

**Request:**
```json
{
  "email": "manager@acme.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "store_manager",
  "branch_id": "br_001",
  "store_id": "st_001",
  "phone": "+1-555-0199",
  "password": "TempPass123!"
}
```

### 4.2 List Users
**Endpoint:** `GET /users?role=store_manager&status=active`

### 4.3 Get User
**Endpoint:** `GET /users/{user_id}`

### 4.4 Update User
**Endpoint:** `PATCH /users/{user_id}`

### 4.5 Deactivate User (soft delete)
**Endpoint:** `DELETE /users/{user_id}`

Deactivates the user (`is_active=false`), revokes sessions, and audits `user_deactivated`. The user row is **not** removed (ADR-003). Reactivate with `PATCH /users/{user_id}` and `{"is_active": true}`.

There is no hard-delete endpoint and no `PATCH /users/{user_id}/status` shortcut.

### 4.6 Roles & Permissions

**List Roles:** `GET /roles`

**Get Role Permissions:** `GET /roles/{role_id}/permissions`

**Update Permissions:** `PUT /roles/{role_id}/permissions`

**Request:**
```json
{
  "module_permissions": ["inventory", "sales", "pos"],
  "menu_permissions": ["products", "stock_in", "stock_out"],
  "record_permissions": {
    "products": ["read", "write", "delete"],
    "sales": ["read", "write"]
  }
}
```

**Available Roles:**
- `super_admin`
- `company_admin`
- `store_manager`
- `sales_officer`
- `inventory_officer`
- `accountant`
- `cashier`

---

## 5. Inventory & Products

Stage 17 C1 proves catalog fidelity for BR-5.1 (categories tree, brands+logo, UoM conversion, variants, barcode generate, multi-image primary, batch/expiry via stock-in) — `test_catalog_fidelity_c1.py`; plan `docs/STAGE_17_PLAN.md`.

### 5.1 Product Categories
**List:** `GET /catalog/categories` (`?tree=true` for nested tree)  
**Create:** `POST /catalog/categories` — body `{ code, name, parent_id?, tax_rate_id? }`  
**Update:** `PATCH /catalog/categories/{category_id}` — may set/clear `tax_rate_id`  
**Delete:** `DELETE /catalog/categories/{category_id}` (soft deactivate)

Stage 10 T1: optional `tax_rate_id` on the category. Tax resolution for a product line is exempt → line override → product `tax_rate_id` → category rate (walks parents) → tenant default.

### 5.2 Brands
**List:** `GET /catalog/brands`  
**Create:** `POST /catalog/brands`  
**Update:** `PATCH /catalog/brands/{brand_id}`

### 5.3 Units
**List:** `GET /catalog/units`  
**Create:** `POST /catalog/units`

### 5.4 Products
**List:** `GET /products`  
**Create:** `POST /products`  
**Get:** `GET /products/{product_id}`  
**Update:** `PATCH /products/{product_id}` (set `is_active=false` to soft-deactivate)  
**Import:** `GET /products/import/template`, `POST /products/import?dry_run=true|false`  
**Warehouse stock:** `GET /products/{product_id}/warehouse-stock`  
**Barcode lookup:** `GET /inventory/products/lookup?q=&barcode=`

Stage 19 P1 proves products/catalog CRUD + import + stock/barcode surfaces via JWT and X-API-Key reads — `test_products_customers_api_p1.py` (BR-18.2). Dedicated catalog CSV export deferred (list/report packaging covers export needs for MVP).

Stage 17 A1 domain audit (`module=inventory`): `product_create` (details.after snapshot); `product_update` / soft-delete `product_deactivate` with `before`/`after` field diffs; stock ops emit `stock_{movement_type}` with qty before/after. Evidence: `test_inventory_audit_a1.py`.

**Create Product Request:**
```json
{
  "name": "Organic Wheat Flour",
  "sku": "WF-ORG-5KG",
  "barcode": "8901234567890",
  "category_id": "cat_001",
  "brand_id": "brand_001",
  "unit_id": "unit_001",
  "variants": [
    {
      "name": "5kg Pack",
      "sku": "WF-ORG-5KG",
      "price": 12.99,
      "cost": 8.50,
      "barcode": "8901234567890"
    }
  ],
  "description": "Premium organic wheat flour",
  "images": ["https://cdn.ribdigi.com/products/wf1.jpg"],
  "track_inventory": true,
  "is_active": true
}
```

### 5.5 Stock Operations

Stage 17 S1 proves stock-in → warehouse qty + `stock_movements`, adjustment reason codes, and opening stock — `test_stock_ops_chain_s1.py`.

**Stock In:** `POST /inventory/stock-in` — body `{ product_id, quantity, warehouse_id?, notes?, variant_id?, batch_number?, manufacturing_date?, expiry_date? }`

**Stock Out:** `POST /inventory/stock-out` — same shape; optional `batch_id` (FEFO if omitted)

**Stock Adjustment:** `POST /inventory/adjust/{product_id}` — body `{ quantity` (signed delta), `reason` (`damage|theft|expiry|found|lost|other`), `notes?`, `warehouse_id?` }. Invalid reason → `400 INVALID_ADJUSTMENT_REASON`.

**Opening Stock:** `POST /inventory/opening-stock` — single or `items[]`; `mode=add|set`; writes `movement_type=opening_stock` / `reference_type=opening_stock`.

**Warehouse stock view:** `GET /products/{product_id}/warehouse-stock`

**Stock Transfer:** `POST /inventory/stock-transfers`

Stage 17 W1: inter-warehouse create → submit/ship → receive updates `WarehouseStock` and writes `transfer_out`/`transfer_in` movements (`reference_type=stock_transfer`). Per-product grid: `GET /products/{id}/warehouse-stock`. Insufficient source qty on ship → `409 INSUFFICIENT_WAREHOUSE_STOCK` (stays `requested`). Evidence: `test_warehouse_transfer_chain_w1.py`.

```json
{
  "from_warehouse_id": "wh_001",
  "to_warehouse_id": "wh_002",
  "submit": true,
  "notes": "Transfer to branch warehouse",
  "items": [{ "product_id": "prod_001", "quantity": 50 }]
}
```

**List:** `GET /inventory/stock-transfers` (filters: `status`, `store_id`, dates, `scope`, `limit`)  
**Submit / Ship / Receive / Cancel:** `POST /inventory/stock-transfers/{transfer_id}/submit|ship|receive|cancel`  
(No status PATCH — use action POSTs.)

**Update Transfer Status:** `PATCH /inventory/stock-transfers/{transfer_id}` — **deprecated / not implemented**; use action POSTs above.
### 5.6 Stock Count

Stage 17 S2 proves create → enter counted qty → complete (posts `adjustment` movements with `reference_type=stock_count`) → variance report export — `test_stock_count_chain_s2.py`.

**Create:** `POST /inventory/stock-counts` — `{ warehouse_id, notes?, product_ids? }` → `status=draft`  
**List:** `GET /inventory/stock-counts`  
**Get:** `GET /inventory/stock-counts/{count_id}` — includes items + line `variance`  
**Update counts:** `PATCH /inventory/stock-counts/{count_id}/items` — `{ items: [{ product_id, counted_qty, notes? }] }` (draft only)  
**Complete:** `POST /inventory/stock-counts/{count_id}/complete` — posts non-zero variances; `status=completed`  
**Cancel:** `POST /inventory/stock-counts/{count_id}/cancel` — draft only → `cancelled`  
**Variance report:** `GET /inventory/stock-counts/{count_id}/variance-report?format=csv|pdf|json` — requires `completed` (`409 COUNT_NOT_COMPLETED` otherwise)

### 5.7 Stock Movement History
**Endpoint:** `GET /inventory/movements?product_id=&warehouse_id=&movement_type=&from_date=&to_date=`  
**Report / export:** `GET /reports/inventory/movements` · export `report_type=inventory_movements` (CSV/PDF)

Stage 17 D1: movements are append-only (`quantity_before` / `quantity_after`, `created_by`); filters cover product, warehouse, type, dates; no delete API. Evidence: `test_stock_integrity_i5.py`, `docs/STAGE_17_FIDELITY.md`.

### 5.8 Low Stock Alerts
**Endpoint:** `GET /inventory/low-stock`  
**Reorder PO:** `POST /inventory/low-stock/reorder-po` (requires `purchasing:write`)

Stage 17 L1: traffic-light `stock_status` (`green`/`yellow`/`red`), `suggested_order_qty`, product + warehouse scopes; draft PO from suggestion. Warehouse thresholds via `PUT /stores/{store_id}/reorder-policy`. Evidence: `test_low_stock_reorder_l1.py`.

**Low-stock list response (`data` is an array):**
```json
{
  "success": true,
  "data": [
    {
      "id": "prod_001",
      "sku": "FLOUR-01",
      "name": "Organic Wheat Flour",
      "stock_qty": 5,
      "minimum_stock": 20,
      "reorder_level": 30,
      "stock_status": "red",
      "suggested_order_qty": 25,
      "scope": "product",
      "warehouse_id": null
    }
  ]
}
```

**Create draft reorder PO:**
```json
{
  "product_id": "prod_001",
  "supplier_id": "sup_001",
  "quantity": 25,
  "warehouse_id": null,
  "unit_price": null,
  "notes": null
}
```
Omitting `quantity` uses the product suggested order qty; omitting `unit_price` uses `cost_price`. Cross-tenant supplier → `404`.

### 5.9 Set Stock Levels
**Product:** `PATCH /products/{product_id}` with `minimum_stock` / `reorder_level`  
**Warehouse (store-linked):** `PUT /stores/{store_id}/reorder-policy`

```json
{
  "product_id": "prod_001",
  "minimum_stock": 20,
  "reorder_level": 30,
  "reorder_qty": 100
}
```

---

## 6. Purchasing

Stage 19 S1 purchasing fidelity: `test_sales_purchases_api_s1.py` (BR-18.5).
 & Suppliers

### 6.1 Suppliers
**List:** `GET /suppliers`  
**Create:** `POST /suppliers`  
**Get:** `GET /suppliers/{supplier_id}`  
**Update:** `PATCH /suppliers/{supplier_id}`  
**Delete:** `DELETE /suppliers/{supplier_id}`

**Create Supplier:**
```json
{
  "name": "Global Supplies Inc",
  "contact_person": "Jane Smith",
  "email": "jane@globalsupplies.com",
  "phone": "+1-555-0200",
  "address": "456 Supply Ave, Industrial City",
  "tax_id": "TAX123456",
  "payment_terms": "net_30",
  "opening_balance": 0.00,
  "status": "active"
}
```

### 6.2 Purchase Request
**List:** `GET /purchasing/requests`  
**Create:** `POST /purchasing/requests`  
**Get:** `GET /purchasing/requests/{request_id}`  
**Approve:** `POST /purchasing/requests/{request_id}/approve`  
**Reject:** `POST /purchasing/requests/{request_id}/reject`

**Create Request:**
```json
{
  "request_date": "2026-08-07",
  "required_date": "2026-08-14",
  "warehouse_id": "wh_001",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 100,
      "notes": "Urgent restock"
    }
  ],
  "notes": "Monthly inventory replenishment"
}
```

### 6.3 Purchase Order
**List:** `GET /purchasing/orders`  
**Create:** `POST /purchasing/orders`  
**Get:** `GET /purchasing/orders/{order_id}`  
**Send:** `POST /purchasing/orders/{order_id}/send`  
**Cancel:** `POST /purchasing/orders/{order_id}/cancel`

**Create PO:**
```json
{
  "supplier_id": "sup_001",
  "order_date": "2026-08-07",
  "expected_delivery": "2026-08-14",
  "warehouse_id": "wh_001",
  "reference": "PO-2026-001",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 100,
      "unit_price": 8.50,
      "tax_rate": 10.0,
      "discount": 0.0
    }
  ],
  "notes": "Standard monthly order"
}
```

**Status Flow:** `draft` → `sent` → `partially_received` → `received` → `cancelled`

### 6.4 Goods Received Note (GRN)
**List:** `GET /purchasing/grn`  
**Create:** `POST /purchasing/grn`  
**Get:** `GET /purchasing/grn/{grn_id}`

**Create GRN** (posts immediately — stock ↑, supplier balance ↑, Dr 1200 / Cr 2000):
```json
{
  "purchase_order_id": "po_001",
  "warehouse_id": "wh_001",
  "items": [
    {
      "po_item_id": "poi_001",
      "received_qty": 100,
      "accepted_qty": 98,
      "rejected_qty": 2,
      "rejection_reason": "Damaged packaging",
      "batch_number": "LOT-1",
      "expiry_date": "2027-01-01T00:00:00"
    }
  ],
  "notes": "Delivery received in good condition"
}
```

Accepted value uses PO line discount + tax math (Stage 11 C1). Uninvoiced AP aging uses received value, not full PO total.

### 6.5 Purchase Invoice
**List:** `GET /purchasing/invoices`  
**Create:** `POST /purchasing/invoices`  
**Get:** `GET /purchasing/invoices/{invoice_id}`  

Supplier payments: `POST /suppliers/{id}/payments` (credit module). Attachment: `POST/GET/DELETE /purchasing/invoices/{invoice_id}/attachment`.

**OCR suggest:** `POST /purchasing/invoices/{invoice_id}/ocr-suggest` — requires `purchasing:write`  
**OCR apply (Stage 10 A1):** `POST /purchasing/invoices/{invoice_id}/ocr-apply` — requires `purchasing:write`

```json
{
  "confirm": true,
  "supplier_invoice_number": "SUP-42",
  "notes": "From OCR",
  "invoice_date": "2026-03-10T00:00:00",
  "due_date": null
}
```

`confirm` must be `true`. Applies only while the invoice is `draft` (409 otherwise). Suggest remains read-only; there is no silent auto-write from OCR.

### 6.6 Purchase Return
**List:** `GET /purchasing/returns`  
**Create:** `POST /purchasing/returns`  
**Get:** `GET /purchasing/returns/{return_id}`  
**Post:** `POST /purchasing/returns/{return_id}/post`

---

## 7. Sales & Customers

Stage 19 S1 proves sales quotations/orders/invoices/payments/returns/POS and purchasing suppliers/PR/PO/GRN/PI/payments via JWT (+ X-API-Key reads) — `test_sales_purchases_api_s1.py` (BR-18.4–18.5).


### 7.1 Customers
**List:** `GET /customers`  
**Create:** `POST /customers`  
**Get:** `GET /customers/{customer_id}` (includes `balance`)  
**Update:** `PATCH /customers/{customer_id}`  
**Delete:** `DELETE /customers/{customer_id}` (soft-deactivate → `status=inactive`)  
**History:** `GET /customers/{customer_id}/history`  
**Outstanding:** `GET /customers/{customer_id}/outstanding` (`credit:read`)

Stage 19 P1 proves customers/groups CRUD + balance + history via JWT and X-API-Key sales reads — `test_products_customers_api_p1.py` (BR-18.3).

**Create Customer:**
```json
{
  "name": "Walk-in Customer",
  "email": "walkin@example.com",
  "phone": "+1-555-0300",
  "address": "789 Customer Lane",
  "party_type": "registered",
  "customer_group_id": "group_uuid",
  "credit_limit": 500.00
}
```

### 7.2 Customer Groups
**List:** `GET /customers/groups`  
**Create:** `POST /customers/groups`  
**Get:** `GET /customers/groups/{group_id}`  
**Update:** `PATCH /customers/groups/{group_id}`  
**Delete:** `DELETE /customers/groups/{group_id}`

### 7.3 Quotations
**List:** `GET /sales/quotations`  
**Create:** `POST /sales/quotations`  
**Get:** `GET /sales/quotations/{quote_id}`  
**Convert to Order:** `POST /sales/quotations/{quote_id}/convert-to-order`

**Create Quotation:**
```json
{
  "customer_id": "cust_001",
  "quote_date": "2026-08-07",
  "expiry_date": "2026-08-14",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "unit_price": 12.99,
      "discount": 1.00,
      "tax_rate": 10.0
    }
  ],
  "notes": "Special pricing for bulk order"
}
```

### 7.4 Sales Orders
**List:** `GET /sales/orders`  
**Create:** `POST /sales/orders`  
**Get:** `GET /sales/orders/{order_id}`  
**Update Status:** `PATCH /sales/orders/{order_id}/status`  
**Convert to Invoice:** `POST /sales/orders/{order_id}/convert-to-invoice`

**Status Flow:** `draft` → `confirmed` → `processing` → `shipped` → `delivered` → `cancelled`

### 7.5 Invoices
**List:** `GET /sales/invoices`  
**Create:** `POST /sales/invoices`  
**Get:** `GET /sales/invoices/{invoice_id}`  
**Post:** `POST /sales/invoices/{invoice_id}/post`  
**Pay:** `POST /sales/invoices/{invoice_id}/payments`  
**Print:** `GET /sales/invoices/{invoice_id}/print`

**Post stock integrity (Stage 15 H1):** Aggregated line quantities are checked before stock-out / AR / journal. Insufficient available stock → `409` with `detail.code = INSUFFICIENT_STOCK`; invoice stays `draft` (no movements, AR bump, or JE).

**Post GL (Stage 15 I1):** Auto journal debits AR `1100`, credits Revenue `4000` (+ Tax `2100` when applicable), and when standard cost > 0 also Dr COGS `5000` / Cr Inventory `1200` (qty × product/variant `cost_price`). Same COGS helper applies to POS sale journals.

**Post audit (Stage 15 A1):** Domain audit `invoice_posted` (`module=sales`) includes tax, stock qty out, customer balance, currency/FX, store.

**Post (credit-limit override):** When posting would push customer AR over `credit_limit`, the API returns `409` with `detail.code=CREDIT_LIMIT_EXCEEDED` and projection fields. Callers with `credit:approve` may retry with:

```json
{
  "credit_limit_override": true,
  "credit_override_reason": "Approved by store manager — VIP order"
}
```

Reason must be at least 3 characters (`400 CREDIT_OVERRIDE_REASON_REQUIRED`). Missing permission → `403 CREDIT_OVERRIDE_FORBIDDEN`. Successful override writes audit action `credit_limit_override` and sets invoice `credit_limit_overridden` / `credit_override_reason` / `credit_override_by` / `credit_override_at`.

**Create Invoice:**
```json
{
  "customer_id": "cust_001",
  "order_id": "so_001",
  "invoice_date": "2026-08-07",
  "due_date": "2026-08-14",
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "unit_price": 12.99,
      "discount": 1.00,
      "tax_rate": 10.0
    }
  ],
  "payment_method": "cash",
  "notes": "Thank you for your business"
}
```

### 7.6 Sales Return
**List:** `GET /sales/returns`  
**Create:** `POST /sales/returns`  
**Get:** `GET /sales/returns/{return_id}`  
**Post:** `POST /sales/returns/{return_id}/post`

**Post (Stage 15 R1/A1):** Restock sellable lines into the original invoice’s store warehouse when `store_id` is set. Customer balance and return journal amounts use `to_base` via the invoice `exchange_rate` (document `paid_amount` stays in doc currency). Journal includes tax reverse `2100`, COGS/Inventory reverse when restocked, and `store_id`. Allocates credit note number. Domain audit `sales_return_posted`.

**Create Return:**
```json
{
  "sales_invoice_id": "inv_001",
  "reason": "defective",
  "restock": true,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 1,
      "condition": "sellable"
    }
  ]
}
```

---

## 8. Point of Sale (POS)

### 8.1 POS Session
**Open Shift:** `POST /pos/sessions/open`

```json
{
  "store_id": "st_001",
  "opening_cash": 200.00,
  "user_id": "usr_001"
}
```

**Close Shift:** `POST /pos/sessions/{session_id}/close`

```json
{
  "closing_cash": 850.50,
  "actual_cash": 845.00,
  "notes": "Minor discrepancy"
}
```

**Get Current Session:** `GET /pos/sessions/current`

### 8.2 POS Sale
**Create Sale:** `POST /pos/sales` — requires `pos:write`

Single tender: set `payment_method` (`cash`|`card`|`wallet`|`credit`|`other`).  
Split tender: set `payments[]` with `{ "payment_method", "amount", "reference?", "liquid_account_id?" }` summing to the computed sale total (`PAYMENT_TOTAL_MISMATCH` if not). Response includes `payments` rows and `payment_method` (`split` when multiple). Credit portion only increases customer AR balance.

Credit tender (full or split portion) enforces the same credit-limit gate as invoice post. Optional body fields: `credit_limit_override` (bool), `credit_override_reason` (string). Same `CREDIT_LIMIT_*` error codes and audit action apply.

**Stock integrity (Stage 13 H1):** Aggregated line quantities are checked before the sale transaction is created. Insufficient available stock returns `409` with `detail.code = INSUFFICIENT_STOCK`. No `Transaction`, `PosPayment`, or `pos_sale` journal is committed; open session totals are unchanged.

**Drawer (Stage 13 H2):** When any tender is `cash` (`has_cash_tender`), the response may include `drawer` (mock/network/browser_bridge pulse per store settings). Card/wallet-only splits omit `drawer`.

**Domain audit:** successful sale records `pos_sale_completed`.

```json
{
  "session_id": "sess_001",
  "party_id": "cust_001",
  "discount_amount": 1.00,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 2,
      "discount": 0.50
    }
  ],
  "payments": [
    { "payment_method": "cash", "amount": 20.00 },
    { "payment_method": "card", "amount": 5.48 }
  ]
}
```

### 8.3 Product Search
**Endpoint:** `GET /pos/products/search?q=flour&barcode=8901234567890`

### 8.4 Receipt Printing & Send
**Get receipt:** `GET /pos/sales/{sale_id}/receipt` — requires `pos:read`

**Query Params:** `format=json|text|pdf` (default `json`); `paper=thermal_80|thermal_58` (tenant default when omitted). JSON includes thermal `text` plus ESC/POS drawer kick bytes (`drawer_kick_base64` / `drawer_kick_hex`).

**Send digital receipt (Stage 13 H2):** `POST /pos/sales/{sale_id}/receipt/send` — requires `pos:write`

**Query Params:** `channel=email|sms` (default `email`); `to` optional recipient (defaults to cashier email/phone); `paper` optional.

Successful send records domain audit `pos_receipt_sent` (`module=pos`, `entity=pos_sale`). Email/SMS uses SMTP/Twilio when configured, otherwise console mode in non-production.

### 8.5 Cash Drawer
**Summary:** `GET /pos/sessions/{session_id}/drawer` — requires `pos:read`  
**Manual open:** `POST /pos/sessions/{session_id}/drawer/open` — requires `pos:write`  
**Store settings:** `PATCH /stores/{store_id}/drawer` — `drawer_mode` `none|mock|network|browser_bridge`, `drawer_open_on_cash`, optional `drawer_host`/`drawer_port`

---

## 9. Expense Management

Stage 22 D1 fidelity for BR-9: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 9.1 Expense Categories
**List:** `GET /expenses/categories`  
**Create:** `POST /expenses/categories`  
**Update:** `PATCH /expenses/categories/{category_id}`  
**Budgets (Stage 22 E1):** `GET /expenses/budgets`

Create/update accept optional `account_id` (tenant expense-type COA; Stage 14 E1) and `budget_amount` (Stage 22 E1). Serialize includes `account_id`, `account_code`, `account_name`. Clear mapping with `clear_account: true` on PATCH. Invalid non-expense account → `400 INVALID_EXPENSE_ACCOUNT`.

### 9.2 Expenses
**List:** `GET /expenses?store_id=&department_id=`  
**Create:** `POST /expenses`  
**Get:** `GET /expenses/{expense_id}`  
**Update:** `PATCH /expenses/{expense_id}`  
**Approve:** `POST /expenses/{expense_id}/approve`  
**Reject:** `POST /expenses/{expense_id}/reject` — body `{ "reason" }`  
**Delete:** `DELETE /expenses/{expense_id}`  
**Approval settings (Stage 22 A1):** `GET/PATCH /expenses/settings` — levels, thresholds, role gates (expense approval matrix)  
**OCR suggest:** `POST /expenses/{expense_id}/ocr-suggest` — requires `expenses:write`  
**OCR apply (Stage 10 A1):** `POST /expenses/{expense_id}/ocr-apply` — requires `expenses:write`

Create/update accept optional `store_id`, `department_id`, `payee` (Stage 14 E2). Foreign store/department → `404`. Approve/reject emit domain audit `expense_approved` / `expense_rejected` (`module=expenses`); submit pending → `expense_submitted`; under-threshold → `expense_auto_approved`; mid-level → `expense_level_approved` (Stage 14 A3). Final/auto approve also posts `journal_posted` with `source_type=expense`.

```json
{
  "confirm": true,
  "amount": 75.5,
  "payee": "Office Depot",
  "description": "Receipt — Office Depot",
  "reference": "R-9",
  "expense_date": "2026-04-01T00:00:00",
  "category_id": null,
  "payment_method": null
}
```

`confirm` must be `true`. Applies only to `pending`/`rejected` expenses (same gate as `PATCH`). Suggest remains read-only; human review is required before apply.

**Create Expense:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "expense_date": "2026-08-07",
  "payment_method": "bank_transfer",
  "reference": "UTIL-001",
  "payee": "City Power",
  "description": "Monthly electricity bill",
  "store_id": "store_001",
  "department_id": "dept_001"
}
```

### 9.3 Recurring Expenses
**List:** `GET /expenses/recurring`  
**Create:** `POST /expenses/recurring`  
**Update:** `PATCH /expenses/recurring/{id}`  
**Generate (Stage 22 A1):** `POST /expenses/recurring/generate`

Templates carry optional `store_id` / `department_id` into generated expenses (Stage 14 E2). `PATCH` supports `skip_next`, `next_amount`, `next_description` (Stage 22 A1).

**Create Recurring:**
```json
{
  "category_id": "exp_cat_001",
  "amount": 150.00,
  "frequency": "monthly",
  "start_date": "2026-08-01",
  "end_date": "2026-12-31",
  "description": "Recurring utility payment"
}
```

---

## 10. Accounting

Stage 22 D1 fidelity for BR-10: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`). Seeded system COA is industry-agnostic for MVP (Stage 22 C1).

### 10.1 Chart of Accounts
**List:** `GET /accounting/accounts` (`tree=true` for nested children; `active_only` default true)  
**Create:** `POST /accounting/accounts`  
**Get:** `GET /accounting/accounts/{account_id}`  
**Update:** `PATCH /accounting/accounts/{account_id}`  
**Opening balance:** `POST /accounting/accounts/{account_id}/opening-balance`

**Account Types:** `asset`, `liability`, `equity`, `income`, `expense`

**Create body:** `{ "code", "name", "account_type", "parent_id?" }` — non-system accounts only. Parent must share `account_type`; cycles rejected.

**Opening balance body:** `{ "amount", "description?" }` — natural-side amount (assets/expenses debit; liability/equity/income credit). Posts balanced journal against system account `3900` Opening Balances Equity (`source_type=opening_balance`). Duplicate posted opening balance → `409 OPENING_BALANCE_EXISTS`.

### 10.2 Journal Entries
**List:** `GET /accounting/journal-entries?store_id=`  
**Create:** `POST /accounting/journal-entries`  
**Get:** `GET /accounting/journal-entries/{entry_id}`  
**Unpost:** `POST /accounting/journal-entries/{entry_id}/unpost`  
**Upload attachment (Stage 9 J1):** `POST /accounting/journal-entries/{entry_id}/attachment` (multipart `file`) — requires `accounting:write`  
**Download attachment:** `GET /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:read`  
**Delete attachment:** `DELETE /accounting/journal-entries/{entry_id}/attachment` — requires `accounting:write`  

Journal payloads include `attachment_url`, `has_attachment`, and optional `store_id` (Stage 14 A1). Manual create accepts `store_id` (tenant-scoped 404). Auto-post from expense / sales invoice / POS sets store when known. Sales invoice / POS / sales return journals include standard-cost COGS↔Inventory lines when cost > 0 (Stage 15 I1); returns also carry invoice `store_id` (Stage 15 R1). List filter `store_id` returns matching entries only. Upload replaces any prior stored object for the entry. Download returns `404` when none is stored.

Unpost reverses account balances and sets status `unposted`. Allowed only when `entry_date` is in the tenant’s open fiscal year (`fiscal_year_start` MM-DD). Returns `409` with `FISCAL_PERIOD_CLOSED`, `JOURNAL_NOT_POSTED`, or `JOURNAL_RECONCILED` when blocked.

**Create Journal Entry:**
```json
{
  "date": "2026-08-07",
  "reference": "JE-001",
  "description": "Adjusting entry for depreciation",
  "entries": [
    {
      "account_id": "acc_001",
      "debit": 100.00,
      "credit": 0.00
    },
    {
      "account_id": "acc_002",
      "debit": 0.00,
      "credit": 100.00
    }
  ]
}
```

### 10.3 Cash & Bank Accounts / Account ledger
**Liquid accounts (Stage 22 B1):** `GET/POST /accounting/liquid-accounts`, `PATCH /accounting/liquid-accounts/{account_id}` — cash/bank with optional `bank_name` / `account_number` / `bank_branch`  
**Liquid transfers:** `POST /accounting/liquid-transfers` — `deposit` / `withdrawal` / `transfer`  
**Bank statements / recon:** `GET/POST /accounting/bank-statements`, `POST .../import`, match/ignore/complete lines (Open Banking adapters deferred)  
**Cheques:** `GET/POST /accounting/cheques` + issue/deposit/bounce/clear lifecycle  
**List (COA filter):** `GET /accounting/accounts?type=asset&sub_type=cash`  
**Create:** `POST /accounting/accounts`  
**Get Transactions (Stage 8 A1):** `GET /accounting/accounts/{account_id}/transactions`

Query: `from_date`, `to_date` (ISO date), `include_unposted` (default false). Returns account metadata, `opening_balance` (activity before `from_date`), `closing_balance`, `total_debit` / `total_credit`, and `transactions[]` with `entry_number`, `entry_date`, debit/credit, and running `balance` on the account’s natural side (assets/expenses: debit−credit; liability/equity/income: credit−debit). Requires `accounting:read`.

### 10.4 Financial Reports
**Profit & Loss:** `GET /reports/profit-loss?from_date=&to_date=&store_id=&branch_id=&compare=` (also `GET /accounting/profit-loss`)  

Returns period totals from **posted** journal lines: `revenue`, `cogs`, `gross_profit`, `operating_expenses`, `other_income`, `income`, `expense`, `net_profit`, plus per-account `bucket`. Optional `store_id` / `branch_id` filter journals by store dimension (Stage 14 A1 store; Stage 23 F1 branch). Foreign store/branch → `404`. Store not in branch → `400 STORE_BRANCH_MISMATCH`. Stage 23 C1: `compare=true` adds `comparison` with equal-length prior period + per-metric `current` / `prior` / `change_pct` (defaults to current calendar month when dates omitted).

**Cash Flow:** `GET /reports/cash-flow?from_date=&to_date=&store_id=&branch_id=&compare=`  

Liquid (cash/bank) movements classified as `operating` / `investing` / `financing` / `transfer` by journal `source_type`. Includes `opening_cash`, `closing_cash`, `net_change` (excludes cash↔bank transfers). Optional `store_id` / `branch_id` (Stage 14 A1 / Stage 23 F1). Stage 23 C1: `compare=true` prior-period `comparison` block (same semantics as P&L).

**Trial Balance:** `GET /reports/trial-balance?as_of_date=` (also `GET /accounting/trial-balance`)  

When `as_of_date` is set, balances are rebuilt from **posted** journal lines with `entry_date` through that day; omit for live account balances. Response includes `as_of` (Stage 14 A2).

**Balance Sheet (Stage 23 F1/C1):** `GET /reports/balance-sheet?as_of_date=&store_id=&branch_id=&compare=`  

Same `as_of_date` semantics as trial balance; response includes `as_of`, `store_id`, `branch_id`, assets/liabilities/equity, and `balanced`. With store/branch filters, balances rebuild from posted journals (tenant live balances are not store-scoped). Empty branch (no stores) returns a zeroed balanced sheet. Stage 23 C1: `compare=true` compares against the same calendar day one month earlier (`comparison.mode=prior_as_of`).

**Export (Stage 22 P1 / Stage 23 F1/C1):** `GET /reports/export?report_type=profit_loss|trial_balance|balance_sheet|cash_flow&format=pdf|xlsx` (also CSV where supported) with optional `store_id` / `branch_id` / `compare`. AR/AP aging via `GET /credit/aging?kind=receivable|payable`.

---

## 11. Credit Management

Stage 22 D1 fidelity for BR-11: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 11.1 Customer Credit
**Get Credit Info:** use customer `balance` on `GET /customers/{customer_id}` plus `GET /credit/customers/{customer_id}/statement` (`credit:read`) — there is no `GET /customers/{customer_id}/credit` route.  
**Aging:** `GET /credit/aging?kind=receivable|payable`  
**Credit limit (Stage 22 R1):** `PATCH /customers/{customer_id}/credit-limit` — block on exceed (`CREDIT_LIMIT_EXCEEDED`); override with `credit_limit_override` + reason + `credit:approve`

**Response:**
```json
{
  "success": true,
  "data": {
    "credit_limit": 500.00,
    "outstanding_balance": 350.00,
    "available_credit": 150.00,
    "credit_sales": [
      {
        "invoice_id": "inv_001",
        "amount": 200.00,
        "due_date": "2026-08-14",
        "status": "outstanding"
      }
    ]
  }
}
```

**Get Outstanding Bills (Stage 8 S2):** `GET /customers/{customer_id}/outstanding`

Returns open AR invoices (`posted` / `partial` / `sent` / `overdue` with balance > 0): `{ invoice_id, invoice_number, amount, due_date, status, document_type: "sales_invoice" }`. Requires `credit:read`; 404 if customer missing.

**Record Payment:** `POST /customers/{customer_id}/payments` (alias `POST /sales/payments`)

```json
{
  "customer_id": "cust_001",
  "amount": 100.00,
  "payment_method": "cash",
  "sales_invoice_id": "inv_001",
  "reference": "RCP-001",
  "notes": "Partial payment for INV-001"
}
```

Optional `sales_invoice_id` allocates to that invoice only; omit to auto-allocate oldest-first (Stage 14 R1 Credit UI). Wrong customer → `400`.

### 11.2 Supplier Credit
**Get Outstanding Bills (Stage 8 S2):** `GET /suppliers/{supplier_id}/outstanding`

**Payment Schedule (Stage 8 S1 / BR-11.2):** `GET /suppliers/{supplier_id}/payment-schedule`

Returns `{ supplier_id, supplier_name, as_of, total_due, overdue_total, upcoming_total, early_pay, items[] }`. Each item includes `document_type` (`purchase_invoice` | `purchase_order`), amount, `due_date`, `days_until_due`, `schedule_bucket` (`overdue` | `due_today` | `upcoming` | `unscheduled`), and `early_discount` quote for open purchase invoices. Sorted overdue → due today → upcoming. Requires `credit:read`.

**Record Payment:** `POST /suppliers/{supplier_id}/payments`

Optional `purchase_invoice_id` and/or `purchase_order_id`; omit both to auto-allocate oldest open bills then POs (Stage 14 R1).

---

## 12. Tax Management

Stage 22 D1 fidelity for BR-12: `docs/STAGE_22_FIDELITY.md` (`test_stage22_fidelity_d1.py`).

### 12.1 Tax Rates
**List:** `GET /tax/rates?active_only=` (alias `GET /taxes/rates`)  
**Create:** `POST /tax/rates`  
**Get:** `GET /tax/rates/{rate_id}`  
**Update (Stage 14 T1):** `PATCH /tax/rates/{rate_id}` — name/rate/type/mode/components/flags; `is_active: false` deactivates and clears default  
**Set default:** `POST /tax/rates/{rate_id}/default`  
**Calculate (Stage 22 T1):** `POST /tax/calculate` — inclusive/exclusive pricing mode + compound components (`basis: compound`)

**Create Tax Rate:**
```json
{
  "name": "Standard VAT",
  "rate": 10.0,
  "tax_type": "vat",
  "pricing_mode": "exclusive",
  "is_default": true,
  "is_active": true
}
```

### 12.2 Tax Reports
**Endpoint:** `GET /reports/tax?from_date=&to_date=&period=&year=&month=&quarter=`  
**Filing pack:** `GET /reports/tax/filing?from_date=&to_date=&period=&year=&month=&quarter=&jurisdiction=` — jurisdiction-neutral boxes plus optional government mapping when supported (`GH`, `NG`, `KE`)  

`period=monthly|quarterly|annually` resolves bounds from `year` / `month` / `quarter` (defaults to current UTC period). Response includes `period`, `period_year`, `period_month`, `period_quarter` when a preset is used (Stage 14 T1). Explicit `from_date`/`to_date` still work when `period` is omitted.

**Exports:** `tax`, `tax_filing`, `tax_filing_gh`, `tax_filing_ng`, `tax_filing_ke` via `/reports/export` (also surfaced on Reports → Tax UI — Stage 16 R2)  

Government templates are **manual filing workbooks only** — they do not e-file to GRA, FIRS, or KRA iTax portals (Stage 10 T2).

### 12.3 Credit aging export (Stage 16 R2)
**Export:** `GET /reports/export?report_type=credit_aging&format=csv|xlsx|pdf&kind=receivable|payable&as_of_date=`  

Packages existing `/credit/aging` into the Reports export surface (no parallel Credit engine). Default `kind=receivable`. Reports UI Credit tab links to `/credit`.

### 12.4 Transfer history export (Stage 16 M2)
**Report:** `GET /reports/transfers`  
**Export:** `GET /reports/export?report_type=transfer_history&format=csv|xlsx|pdf&status=&store_id=&scope=all|inter_store|warehouse&from_date=&to_date=&limit=`  

Consolidated inter-store + warehouse transfer history (same `StockTransfer` records as `/stores/transfers`). Reports UI **Transfers** tab.

---

## 13. Multi-Store Management

### 13.1 Stores
**List:** `GET /stores`  
**Create:** `POST /stores`  
**Get:** `GET /stores/{store_id}`  
**Update:** `PATCH /stores/{store_id}`

**Create Store:**
```json
{
  "name": "Downtown Store",
  "code": "DT-01",
  "address": "100 Main St",
  "phone": "+1-555-0400",
  "manager_id": "usr_002",
  "warehouse_id": "wh_002",
  "status": "active"
}
```

### 13.2 Store Inventory
**Endpoint:** `GET /stores/{store_id}/inventory`

### 13.3 Store Sales
**Endpoint:** `GET /stores/{store_id}/sales`

Query params: `from_date`, `to_date`, `recent_limit` (default 50, max 200).

Returns store metadata, aggregated `summary` (invoice/POS counts and revenue), and `recent` sale lines (`source` = `invoice`|`pos`). Tenant-scoped; unknown/foreign store → 404. Requires `stores:read`.

Global UI store context (Shell switcher) is client-side only (`localStorage` key `selected_store_id`); it does not send a store header to the API.

### 13.4 Inter-Store Transfers
**List:** `GET /stores/transfers` — optional filters: `status`, `store_id` (from or to), `from_date`, `to_date`, `scope=all|inter_store|warehouse`, `limit` (Stage 16 M2)  
**Create:** `POST /stores/transfers`  
**Get:** `GET /stores/transfers/{transfer_id}`  
**Submit:** `POST /stores/transfers/{transfer_id}/submit`  
**Ship:** `POST /stores/transfers/{transfer_id}/ship`  
**Receive:** `POST /stores/transfers/{transfer_id}/receive`  
**Cancel:** `POST /stores/transfers/{transfer_id}/cancel`

**Transfer history report (Stage 16 M2):** `GET /reports/transfers?status=&store_id=&from_date=&to_date=&scope=all|inter_store|warehouse&limit=` — consolidated counts/`by_status`/qty totals + serialized transfers. Export: `report_type=transfer_history` via `/reports/export`. Reports UI **Transfers** tab.

Status flow: `draft` → `requested` → `in_transit` → `received` (or `cancelled`).

**Dual-manager approval (Stage 4 T1 / BR-13.2):** When the source store has `manager_id`, only that user may ship (`403 TRANSFER_SHIP_FORBIDDEN` otherwise). When the destination store has `manager_id`, only that user may receive (`403 TRANSFER_RECEIVE_FORBIDDEN`). `company_admin` / `super_admin` may override either action; override writes audit action `transfer_manager_override`. Warehouse-only transfers (null store ids) skip this gate. Serialized transfers include `from_store_manager_id` / `to_store_manager_id`.

**Stock chain (Stage 16 M1):** Ship deducts source warehouse stock and writes `stock_movements` (`transfer_out`, `reference_type=stock_transfer`). Receive adds destination warehouse stock (`transfer_in`). Insufficient source qty → `409 INSUFFICIENT_WAREHOUSE_STOCK`; transfer stays `requested` with no movements. Evidence: `test_multistore_transfer_chain_m1.py`.

**Create Transfer:**
```json
{
  "from_store_id": "st_001",
  "to_store_id": "st_002",
  "submit": true,
  "items": [
    {
      "product_id": "prod_001",
      "quantity": 20
    }
  ],
  "notes": "Stock rebalancing"
}
```

---

## 14. Reports

Stage 23 D1 fidelity for BR-14.5 financial filters/comparative + MVP gate docs: `docs/STAGE_23_FIDELITY.md` (`test_stage23_fidelity_d1.py`). Financial endpoints also documented under §10.4.

### 14.1 Sales Reports
**Daily Sales:** `GET /reports/sales/daily?date=` — includes `previous_day_revenue` and `change_pct` vs prior day.  
**Monthly Sales:** `GET /reports/sales/monthly?month=&year=` — includes `previous_month_revenue` and `change_pct`.  
**Product Sales:** `GET /reports/sales/products?from_date=&to_date=&store_id=&category_id=`  
**Customer Sales:** `GET /reports/sales/customers?from_date=&to_date=&limit=` — top customers by revenue and frequency (invoice + POS).  
**Salesperson:** `GET /reports/sales/salesperson?from_date=&to_date=`  
**By Store:** `GET /reports/sales/by-store?from_date=&to_date=`

Export type `sales_customers` is available on `/reports/export`. Product export honors `store_id` / `category_id`.

### 14.2 Inventory Reports
**Stock Balance:** `GET /reports/inventory/balance?warehouse_id=`  
**Stock Movement:** `GET /reports/inventory/movements?product_id=&from_date=&to_date=`  
**Low Stock:** `GET /reports/inventory/low-stock?store_id=&warehouse_id=`  
**Expiry:** `GET /reports/inventory/expiry?days=30`  
**Stock Valuation (Stage 9 R2):** `GET /reports/inventory/valuation?warehouse_id=&store_id=`  

Valuation uses **standard cost** only: `value = quantity × product.cost_price`. Response includes `costing_method` (`standard_cost`), `costing_method_note`, line items, `by_warehouse` totals, and overall `total_value`. FIFO/LIFO/weighted average are **not** implemented. Export type: `inventory_valuation`. Requires `reports:read`. See also `docs/STAGE_9_FIDELITY.md`.

### 14.3 Purchase Reports
**Purchase Summary:** `GET /reports/purchases/summary?from_date=&to_date=`  
**Supplier Purchases:** `GET /reports/purchases/suppliers?supplier_id=&from_date=&to_date=`  
**Pending Orders (Stage 9 R1):** `GET /reports/purchases/pending-orders?supplier_id=&from_date=&to_date=` — issued POs in `sent` or `partially_received` with ordered/received/open quantities  
**Purchase Return Summary (Stage 9 R1):** `GET /reports/purchases/returns?supplier_id=&from_date=&to_date=` — returns by reason/supplier with posted totals  

Export types: `purchases_pending_orders`, `purchases_returns` (plus existing `purchases_summary` / `purchases_suppliers`). Requires `reports:read`.

### 14.4 Expense Reports
**Expense Summary:** `GET /reports/expenses/summary?from_date=&to_date=&category_id=`

### 14.5 Financial Reports (Stage 23 F1/C1)
See §10.4 for `GET /reports/profit-loss`, `/reports/cash-flow`, `/reports/balance-sheet`, `/reports/trial-balance` with `store_id` / `branch_id` / `compare` and export packaging.

---

## 15. Notifications

Stage 21 N1/D1 proves BR-4.4 panel fidelity — unread count, groups, mark read/unread, 90-day history (`test_dashboard_notifications_n1.py`; `docs/STAGE_21_FIDELITY.md`). WebSocket realtime remains deferred.

### 15.1 List Notifications
**Endpoint:** `GET /notifications?status=unread&category=&group=`

Groups: `stock`, `orders`, `payments`, `system`. Category `new_order` (Stage 4 N1 / BR-15.1) belongs to group `orders` and is emitted when a sales order is created or confirmed. List applies a **90-day** `created_at` cutoff (`HISTORY_DAYS`).

**Unread count:** `GET /notifications/unread-count` → `{ count }`.

### 15.2 Mark as Read
**Endpoint:** `PATCH /notifications/{notification_id}/read`  
**Mark unread:** `PATCH /notifications/{notification_id}/unread`  
**Mark all read:** `POST /notifications/read-all`

### 15.3 Notification Settings
**Endpoint:** `GET /notifications/settings`  
**Update:** `PATCH /notifications/settings`

Preference keys include `new_order`, `low_stock`, `purchase_received`, `payment_due`, `credit_limit`, `shift_variance`, `transfer`, and other default categories. Each key has `dashboard` / `email` / `sms` booleans.

```json
{
  "low_stock": { "dashboard": true, "email": false, "sms": false },
  "new_order": { "dashboard": true, "email": false, "sms": false },
  "payment_due": { "dashboard": true, "email": true, "sms": false },
  "credit_limit": { "dashboard": true, "email": false, "sms": false }
}
```

Outline alert categories (`low_stock`, `new_order`, `credit_limit`, `purchase_received`, `shift_variance`, `transfer`) default **email/sms false**; enable per user via this API. `payment_due` / `expense_approval` default email on.

**Channel delivery (Stage 16 N2):** After the dashboard notification is written, `create_notification` best-effort sends email/SMS to recipients with that channel enabled for the category. Broadcast alerts (`user_id` null) target active `company_admin` / `super_admin`. SMTP unset → email `mode=console` outbox attempt; Twilio unset → SMS `mode=console`. Carrier `delivered` is only recorded for real SMTP/Twilio sends.
---

## 16. AI Business Assistant

Stage 20 D1 proves BR-21 commercial-MVP AI fidelity on rule-based `/ai/*` engines — `docs/STAGE_20_FIDELITY.md` (`test_stage20_fidelity_d1.py`). External LLM / Prophet upgrades remain deferred.

### 16.1 AI ERP Chat Assistant
**Endpoint:** `POST /ai/chat`  
**History:** `GET /ai/chat/history`  
**Permission:** `ai:read` (commands that write require the matching module write, e.g. `purchasing:write` for draft PO)

**Request:**
```json
{
  "message": "What are my top selling products this month?",
  "context": "dashboard",
  "conversation_id": "conv_001"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "reply": "Your top selling products this month are: 1. Organic Wheat Flour (245 units), 2. Sugar 1kg (189 units), 3. Rice 5kg (156 units).",
    "suggested_actions": [
      { "type": "navigate", "label": "View Sales Report", "url": "/reports/sales/products" }
    ]
  }
}
```

### 16.2 AI Dashboard Insights
**Endpoint:** `GET /ai/insights`  
Returns anomaly / restock / purchase cards with per-card `domains` cites (Inventory, Sales, Purchases, Expenses). Also returns `actuals`, `actuals_covered`, and `note` (Stage 25 B1). Weekly digest via Celery/`publish_insights` when email prefs allow. Evidence: `test_ai_insights_fidelity_i1.py`, `test_ai_business_insights_b1.py`.

### 16.3 Smart Inventory Intelligence
**Endpoints:**  
- `GET /ai/inventory/predictions` — combined forecast + low-stock summary  
- `GET /ai/inventory/demand-forecast` — 7/30/90 demand + reorder + seasonality  
- `GET /ai/inventory/dead-stock` — idle stock identification

### 16.4 AI Low Stock Prediction
**Endpoint:** `GET /ai/inventory/low-stock-prediction?horizon_days=14&lead_time_days=7&lookback_days=30&at_risk_only=true`

### 16.5 AI Sales Analysis
**Endpoint:** `GET /ai/sales/analysis?from_date=&to_date=&lookback_days=90`  
Returns `trend` (incl. 7/14/30 forecast), `rfm`, `product_affinity`, `peaks`.

### 16.6 AI Expense Analysis
**Endpoint:** `GET /ai/expenses/analysis?from_date=&to_date=`

### 16.6a AI Purchases Analysis (Stage 25 P1 / BR-21.11)
**Endpoint:** `GET /ai/purchases/analysis?from_date=&to_date=&lookback_days=90`  
Returns `trend` (incl. 7/14/30 forecast from posted PI totals), `suppliers` (spend share), `purchase_orders` (status/fill), `goods_receipts`, `purchase_invoices.overdue`, and `suggestions`. Method `rules_v1` (not Prophet). Evidence: `test_ai_purchases_analysis_p1.py`. Stage 25 U1 wires this on `frontend/app/ai/page.tsx` (`test_ai_ui_fidelity_u1.py`).

### 16.6b Cross-Domain AI Analysis (Stage 25 X1 / BR-21.12)
**Endpoint:** `GET /ai/cross-domain/analysis?from_date=&to_date=&lookback_days=90`  
Orchestrates inventory / sales / purchases / expenses analyzers. Returns `domains` (per-domain summaries + endpoint cites) and `cross_signals` (multi-domain synthesis). Method `rules_v1`. Evidence: `test_ai_cross_domain_x1.py`. Stage 25 U1 wires this on `frontend/app/ai/page.tsx`.

### 16.7 AI Report Generator
**Endpoint:** `POST /ai/reports/generate` (optional `?export=true` for file download)  
**Templates:** `GET/POST /ai/reports/templates`, `DELETE /ai/reports/templates/{template_id}`

```json
{
  "prompt": "Show me monthly sales for Q2 2026",
  "format": "csv"
}
```

Reuse a saved template with `{ "template_id": "…" }`. Export sets `Content-Disposition` attachment.

### 16.8 AI Document Assistant
**Endpoint:** `POST /ai/documents/analyze`

**Content-Type:** `multipart/form-data` (`file` + query/form `document_type`)

```json
{
  "file": "<uploaded_file>",
  "document_type": "invoice"
}
```

Human-confirmed OCR apply to expense/PI drafts uses the Stage 10 `ocr-apply` paths (`confirm: true`); PO OCR apply remains deferred. Stage 25 U1 wires suggest-only analyze on `frontend/app/ai/page.tsx` (`test_ai_ui_fidelity_u1.py`).

### 16.9 AI Customer Assistant
**Endpoints:**  
- `POST /ai/customer/assist` — NL assist for a customer or portfolio query  
- `GET /ai/customers/insights` — `best_customers`, `churn_risks`, `promotion_suggestions`

```json
{
  "customer_id": "cust_001",
  "query": "What is my current outstanding balance?"
}
```

### 16.10 AI Security Monitor
**Endpoint:** `GET /ai/security/alerts?lookback_hours=72&notify=false`  
`notify=true` creates unread `category=security` notifications for high-score alerts. Requires `security:read`.

---

## 17. Webhooks

RIBDIGI ERP supports webhook subscriptions for real-time event notifications.

### 17.1 Manage Webhooks
**List:** `GET /webhooks`  
**Create:** `POST /webhooks`  
**Get:** `GET /webhooks/{webhook_id}`  
**Update:** `PATCH /webhooks/{webhook_id}`  
**Delete:** `DELETE /webhooks/{webhook_id}`

**Create Webhook:**
```json
{
  "url": "https://your-app.com/webhooks/ribdigi",
  "events": ["sale.created", "stock.low", "payment.received"],
  "secret": "whsec_your_secret",
  "is_active": true
}
```

### 17.2 Available Events

| Event | Description |
|-------|-------------|
| `sale.created` | New sale/invoice created |
| `sale.paid` | Invoice payment received |
| `stock.low` | Product reached low stock level |
| `stock.in` | Stock received into warehouse |
| `purchase.order.created` | New PO created |
| `purchase.grn.received` | GRN recorded |
| `customer.created` | New customer added |
| `expense.approved` | Expense approved |
| `user.login` | User logged in |
| `tenant.suspended` | Tenant account suspended |

### 17.3 Webhook Payload
```json
{
  "event": "sale.created",
  "timestamp": "2026-08-07T13:51:00Z",
  "tenant_id": "tenant_abc123",
  "data": {
    "invoice_id": "inv_001",
    "amount": 250.00,
    "customer_id": "cust_001"
  }
}
```

### 17.4 Signature verification (Stage 6 W1)
Each delivery includes header `X-Ribdigi-Signature` with value `t=<unix_ts>,v1=<hex>` where `v1` is HMAC-SHA256 of `{t}.{raw_body}` using the webhook signing secret (`whsec_…`, shown once on create). Reject if timestamp skew exceeds 5 minutes. Test ping: `POST /webhooks/{id}/test` (`webhook.test` event). Invoice post emits `sale.created`.

### 17.5 Delivery retries (Stage 7 W2)
Non-2xx or transport errors set delivery status to `pending_retry` with `next_retry_at` using exponential backoff (`WEBHOOK_RETRY_BASE_SECONDS` × 5^(attempt−1), capped at 1 hour). Celery beat job `retry_due_webhooks` (also `POST /jobs/retry_due_webhooks/run`) re-signs the stored payload with a fresh timestamp and re-POSTs. After `WEBHOOK_MAX_ATTEMPTS` (default 5) the delivery is terminal `failed`. Successful retry → `delivered` and clears `next_retry_at`.

---

## 18. Caching (Stage 6 P2 / Stage 7 C2)

Read models and resolved permissions may be served from Redis (`CACHE_BACKEND=auto|redis|memory`) with soft fallback:

| Endpoint / path | Key pattern | TTL |
|-----------------|-------------|-----|
| `GET /dashboard` | `ribdigi:cache:dashboard:{tenant_id}:summary` | 5 min |

**Executive dashboard (Stage 21 V1/D1):** `GET /dashboard` returns KPI totals, inventory alerts (`low_stock` / `out_of_stock` / `expiring_batches`), period compare (`daily_revenue` / `yesterday_revenue` / `dod_change_pct` + MoM), `recent_sales` (≤10), `top_products`, `daily_revenue_series` (30) / `monthly_revenue_series` (12), and `kpi_links`. Evidence: `test_dashboard_kpis_v1.py`.

| `GET /products` | `ribdigi:cache:products:{tenant_id}:all` | 10 min |
| `GET /catalog/categories` | `…:categories:flat` / `…:categories:tree` | 10 min |
| Auth claims / `GET /me` | `ribdigi:cache:perms:{tenant_id}:{user_id}` | 1 hour (`CACHE_PERMISSIONS_TTL_SECONDS`) |

Dashboard/catalog invalidated on product/catalog/stock mutations, POS sale, invoice post, and expense approval. Permissions invalidated on user role/`record_scope` change and custom-role updates that sync assigned users. Disable with `CACHE_ENABLED=false`.

## 19. Rate Limits

API requests are rate-limited with a sliding window (Stage 5 S1 / Stage 19 K1). Keys are `{client_ip}:{auth|api}:{X-Tenant-ID|anon}` so tenants sharing an egress IP do not share the same bucket. Caps come from env (`RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_AUTH_PER_MINUTE`); subscription plan-tier tables are deferred post-MVP.

Auth-class paths (stricter `RATE_LIMIT_AUTH_PER_MINUTE`) include login, refresh, 2FA verify, password-reset, email verify, and tenant registration.

**Rate Limit Headers:**
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Backend: memory|redis
```

On `429 RATE_LIMIT_EXCEEDED`, responses also include `Retry-After`. Evidence: `test_production_security_s1.py`, `test_auth_api_fidelity_k1.py`.

---

## 20. Error Codes

### HTTP Status Codes
| Code | Meaning |
|------|---------|
| `200` | OK — Success |
| `201` | Created — Resource created |
| `400` | Bad Request — Invalid input |
| `401` | Unauthorized — Authentication required |
| `403` | Forbidden — Insufficient permissions |
| `404` | Not Found — Resource doesn't exist |
| `409` | Conflict — Resource conflict |
| `422` | Unprocessable Entity — Validation error |
| `429` | Too Many Requests — Rate limit exceeded |
| `500` | Internal Server Error |

### Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Email is required"
      }
    ]
  },
  "request_id": "req_8f3a9b2c1d4e"
}
```

### Common Error Codes
| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Input validation failed |
| `AUTHENTICATION_FAILED` | Invalid credentials |
| `TOKEN_EXPIRED` | JWT token has expired |
| `INSUFFICIENT_PERMISSIONS` | User lacks required role/permission |
| `TENANT_SUSPENDED` | Tenant account is suspended |
| `RESOURCE_NOT_FOUND` | Requested resource not found |
| `INSUFFICIENT_STOCK` | Not enough stock for operation |
| `CREDIT_LIMIT_EXCEEDED` | Customer credit limit reached |
| `DUPLICATE_ENTRY` | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | Too many requests |

---

## Backup & Logical Restore

Stage 5 / 10 / 18 / 23 B1 — encrypted tenant `.ribbak` archives. Requires `company_admin` or `super_admin`. Runbook: `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`. Stage 23 D1 cite: `docs/STAGE_23_FIDELITY.md`.

**Settings:** `GET/PATCH /backup/settings` — `enabled`, `frequency` (`daily`|`weekly`), `retention_count`, `hour_utc`  
**Create:** `POST /backup` — returns `id`, `checksum_sha256`, `filename`  
**List / get / download:** `GET /backup`, `GET /backup/{backup_id}`, `GET /backup/{backup_id}/download` (`X-Checksum-SHA256`)  
**Run due:** `POST /backup/run-due` — schedule runner (`ran` / `reason`; never fake success on failure)  
**Verify:** `POST /backup/{backup_id}/verify` — integrity proof vs live data  
**Restore:** `POST /backup/{backup_id}/restore`  
- Dry-run: `{"dry_run": true}`  
- Apply: `{"dry_run": false, "confirm": true, "confirm_text": "RESTORE"}` (any other `confirm_text` → `400`)  
Foreign-tenant `backup_id` → `404`. WAL / pg_dump / S3 PITR deferred post-MVP. Evidence: `test_logical_dr_drill_b1.py`.

---

## Appendix A: Data Types

| Type | Format | Example |
|------|--------|---------|
| `id` | string | `usr_001`, `prod_abc123` |
| `decimal` | string | `"199.99"` |
| `date` | ISO 8601 | `2026-08-07` |
| `datetime` | ISO 8601 | `2026-08-07T13:51:00Z` |
| `currency` | ISO 4217 | `USD`, `EUR`, `NGN` |
| `status` | string enum | `active`, `inactive`, `pending` |

## Appendix B: Multi-Tenant Headers

All API requests (except tenant registration) must include:

```
X-Tenant-ID: tenant_abc123
Authorization: Bearer <jwt_token>
```

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, JWT + OAuth2

Stage 97 D1 — `docs/STAGE_97_FIDELITY.md` (`test_stage97_fidelity_d1.py`): Stage 97 S1 `GET /sales/invoices?status=`; Stage 97 P1 `GET /purchasing/invoices?status=outstanding`; Stage 97 I1 product labels `code_type=qr`.

Stage 98 D1 — `docs/STAGE_98_FIDELITY.md` (`test_stage98_fidelity_d1.py`): Stage 98 Q1 `GET /expenses?status=`; Stage 98 R1 `GET /sales/returns?status=` / `GET /purchasing/returns?status=`; Stage 98 O1 credit kpi `?kind=`.

Stage 99 D1 — `docs/STAGE_99_FIDELITY.md` (`test_stage99_fidelity_d1.py`): Stage 99 T1 quotations/orders `status=`; Stage 99 C1 PR/PO/GRN `status=` / `open`.

Stage 100 D1 — `docs/STAGE_100_FIDELITY.md` (`test_stage100_fidelity_d1.py`): Stage 100 G1 `GET /accounting/journal-entries?status=`; Stage 100 U1 `GET /users?q=&role=&is_active=`.

Stage 101 D1 — `docs/STAGE_101_FIDELITY.md` (`test_stage101_fidelity_d1.py`): Stage 101 O1 inventory movements `movement_type` URL; Stage 101 P1 `GET /pos/sessions` history UI; Stage 101 E1 notifications `status`/`group` URL sync.

Stage 102 D1 — `docs/STAGE_102_FIDELITY.md` (`test_stage102_fidelity_d1.py`): Stage 102 A1 audit `from_date`/`to_date` URL sync; Stage 102 R1 residual report tab Shell leaves; Stage 102 T1 tax/stores/company deep-links.
Stage 103 D1 — `docs/STAGE_103_FIDELITY.md` (`test_stage103_fidelity_d1.py`): Stage 103 S1 security `#passkeys`/`#webhooks`/`#api-keys`/`#sessions` Shell leaves; Stage 103 B1 backup `#schedule`/`#restore`; Stage 103 C1 company `#branches`/`#document-numbering`/`#media`.
Stage 104 D1 — `docs/STAGE_104_FIDELITY.md` (`test_stage104_fidelity_d1.py`): Stage 104 A1 journal `status`/`store_id` + cheque `direction`/`status` URL filters; Stage 104 I1 Products/Purchase Invoices/Draft/Overdue leaves; Stage 104 R1 credit/roles anchors + `kpi_links.custom_roles`.
Stage 105 D1 — `docs/STAGE_105_FIDELITY.md` (`test_stage105_fidelity_d1.py`): Stage 105 P1 permissions `?role=` + `#system`/`#custom`; Stage 105 S1 stores `#fefo`/`#reorder` + `store_id`; Stage 105 A1 platform audit filter URL + `delivery_only`.
Stage 106 D1 — `docs/STAGE_106_FIDELITY.md` (`test_stage106_fidelity_d1.py`): Stage 106 E1 expense `store_id`/`department_id` URL + purchase-settings hash; Stage 106 C1 company `#logo`/`#profile`/`#locale`/`#departments`; Stage 106 N1 notification inbox leaves.
Stage 107 D1 — `docs/STAGE_107_FIDELITY.md` (`test_stage107_fidelity_d1.py`): Stage 107 P1 POS `#shift`/`#cart`/`#receipt`; Stage 107 S1 sales `active_only` + inventory `q`/`category_id`/`brand_id`; Stage 107 O1 platform at-risk/new tenants + backup `#history`.
Stage 108 D1 — `docs/STAGE_108_FIDELITY.md` (`test_stage108_fidelity_d1.py`): Stage 108 A1 AI analysis Shell leaves; Stage 108 C1 credit `#party-actions`/`#by-party`/`#statement`; Stage 108 U1 users Active/Inactive directory leaves.
Stage 109 D1 — `docs/STAGE_109_FIDELITY.md` (`test_stage109_fidelity_d1.py`): Stage 109 R1 report/tax/movements period URL; Stage 109 S1 sales quote/order/return status leaves; Stage 109 O1 platform status + bank-recon hash.
Stage 110 D1 — `docs/STAGE_110_FIDELITY.md` (`test_stage110_fidelity_d1.py`): Stage 110 P1 purchasing GRN/returns/invoice status leaves; Stage 110 E1 expense approved/rejected queue; Stage 110 A1 Create Role `#create` + Audit `?module=`.
Stage 111 D1 — `docs/STAGE_111_FIDELITY.md` (`test_stage111_fidelity_d1.py`): Stage 111 I1 inventory `movement_type` Shell leaves; Stage 111 S1 Posted Sales Returns; Stage 111 C1 `#cheques` hash + deposited/cleared.
Stage 112 D1 — `docs/STAGE_112_FIDELITY.md` (`test_stage112_fidelity_d1.py`): Stage 112 R1 report schedule frequency/enabled leaves; Stage 112 S1 stores `#cash-drawer`; Stage 112 P1 platform `plan_code` + at-risk hash.
Stage 113 D1 — `docs/STAGE_113_FIDELITY.md` (`test_stage113_fidelity_d1.py`): Stage 113 N1 Read Notifications; Stage 113 C1 bounced/cancelled cheques; Stage 113 S1 shipped/delivered orders + paid invoices + transfer status leaves.
