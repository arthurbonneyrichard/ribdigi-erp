"""Stage 21 D1 — documentation fidelity for tenant/org/dashboard (BR-1–4)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage21_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_21_FIDELITY.md")
    assert "BR-1" in fidelity and "BR-4" in fidelity
    assert "test_tenant_lifecycle_t1.py" in fidelity
    assert "test_tenant_isolation_seeds_i1.py" in fidelity
    assert "test_org_units_o1.py" in fidelity
    assert "test_company_currency_tax_c1.py" in fidelity
    assert "test_users_roles_u1.py" in fidelity
    assert "test_dashboard_kpis_v1.py" in fidelity
    assert "test_dashboard_notifications_n1.py" in fidelity
    assert "test_stage21_fidelity_d1.py" in fidelity
    assert "ADR-047" in fidelity or "ADR_047" in fidelity
    assert "yesterday_revenue" in fidelity or "dod_change_pct" in fidelity
    assert "ADR-001" in fidelity or "shared-schema" in fidelity
    assert "ADR-006" in fidelity
    assert "H21x" in fidelity

    plan = _read("docs/STAGE_21_PLAN.md")
    assert "STAGE_21_FIDELITY.md" in plan
    for ws in ("T1", "I1", "O1", "C1", "U1", "V1", "N1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}**" in ln][0]
        assert "COMPLETE" in line, ws
    h21 = [ln for ln in plan.splitlines() if "| **H21x**" in ln][0]
    assert "PENDING" in h21
    assert "ADR-047" in plan or "ADR_047" in plan


def test_stage21_br_1_to_4_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 21 T1" in br
    assert "Stage 21 I1" in br
    assert "Stage 21 O1" in br
    assert "Stage 21 C1" in br
    assert "Stage 21 U1" in br
    assert "Stage 21 V1" in br
    assert "Stage 21 N1" in br
    assert "Stage 21 D1" in br
    assert "STAGE_21_FIDELITY.md" in br

    s11 = br.split("#### BR-1.1 Tenant Registration")[1].split("#### BR-1.2")[0]
    assert "[x] User can register with company name, email, password, industry type" in s11
    assert "[x] Tenant status defaults to \"Trial\"" in s11

    s14 = br.split("#### BR-1.4 Data Isolation")[1].split("#### BR-1.5")[0]
    assert "[x] Tenant A cannot access Tenant B data" in s14
    assert "ADR-001" in s14 or "shared-schema" in s14

    s21 = br.split("#### BR-2.1 Company Information")[1].split("#### BR-2.2")[0]
    assert "[x] CRUD operations on company legal name" in s21
    assert "[x] Multiple address support" in s21

    s22 = br.split("#### BR-2.2 Branch Management")[1].split("#### BR-2.3")[0]
    assert "[x] Create/edit/delete branches" in s22
    assert "[x] Deactivate branch without data loss" in s22

    s26 = br.split("#### BR-2.6 Currency Setup")[1].split("#### BR-2.7")[0]
    assert "[x] Add currencies with exchange rates" in s26
    assert "[x] Transaction-level currency selection" in s26

    s27 = br.split("#### BR-2.7 Language Configuration")[1].split("#### BR-2.8")[0]
    assert "ADR-006" in s27

    s28 = br.split("#### BR-2.8 Tax Configuration")[1].split("---")[0]
    assert "[x] Add multiple tax rates" in s28
    assert "[x] Compound tax support" in s28

    s31 = br.split("#### BR-3.1 User Account CRUD")[1].split("#### BR-3.2")[0]
    assert "[x] Create user with name, email, phone, role" in s31
    assert "[x] Bulk user import via CSV" in s31
    assert "ADR_003" in s31 or "ADR-003" in s31

    s32 = br.split("#### BR-3.2 Role Management")[1].split("#### BR-3.3")[0]
    assert "[x] Predefined roles" in s32
    assert "[x] Custom role creation capability" in s32

    s41 = br.split("#### BR-4.1 KPI Cards")[1].split("#### BR-4.2")[0]
    assert "[x] Display: Total Sales, Total Purchases, Total Expenses" in s41
    assert "[x] Period comparison" in s41
    assert "dod_change_pct" in s41 or "yesterday_revenue" in s41

    s44 = br.split("#### BR-4.4 Notifications Panel")[1].split("---")[0]
    assert "[x] Display unread notification count" in s44
    assert "[x] Notification history (last 90 days)" in s44


def test_stage21_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 21 D1" in api or "STAGE_21_FIDELITY.md" in api
    assert "/tenants" in api
    assert "/dashboard" in api
    assert "yesterday_revenue" in api or "dod_change_pct" in api
    assert "/notifications" in api
    assert "/notifications/unread-count" in api or "unread-count" in api
    assert "/users" in api
    assert "/roles" in api
    assert "/tax/rates" in api
    assert "test_stage21_fidelity_d1.py" in api or "STAGE_21_FIDELITY.md" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 21" in manual or "STAGE_21_FIDELITY" in manual
    assert "Dashboard" in manual
    assert "Yesterday" in manual or "DoD" in manual or "day-over-day" in manual.lower()
    assert "Notifications" in manual
    assert "90" in manual or "history" in manual.lower()

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_tenant_lifecycle_t1.py" in launch
    assert "test_tenant_isolation_seeds_i1.py" in launch
    assert "test_org_units_o1.py" in launch
    assert "test_company_currency_tax_c1.py" in launch
    assert "test_users_roles_u1.py" in launch
    assert "test_dashboard_kpis_v1.py" in launch
    assert "test_dashboard_notifications_n1.py" in launch
    assert "test_stage21_fidelity_d1.py" in launch
    assert "STAGE_21_FIDELITY.md" in launch
    # Launch §§1–2 still operator-env checklists (not auto-checked by fidelity alone)
    assert "## 1. Configuration & secrets" in launch
    assert "## 2. Identity & security" in launch


def test_stage21_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_21_FIDELITY.md" in pr
    assert "test_stage21_fidelity_d1.py" in pr
    assert "Stage 21 D1" in pr
    assert "test_tenant_lifecycle_t1.py" in pr
    assert "test_dashboard_kpis_v1.py" in pr
    assert "test_dashboard_notifications_n1.py" in pr
    assert "dod_change_pct" in pr or "yesterday_revenue" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_21_FIDELITY.md" in roadmap
    assert "Stage 21 D1" in roadmap
    assert "ADR_047_STAGE21_OPEN.md" in roadmap
    assert "STAGE_21_PLAN.md" in roadmap
