"""Stage 19 D1 — documentation fidelity for API, Settings & Operator Reliability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage19_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_19_FIDELITY.md")
    assert "BR-18" in fidelity and "BR-19" in fidelity and "BR-20" in fidelity
    assert "test_auth_api_fidelity_k1.py" in fidelity
    assert "test_products_customers_api_p1.py" in fidelity
    assert "test_sales_purchases_api_s1.py" in fidelity
    assert "test_api_standards_a1.py" in fidelity
    assert "test_auth_session_br19_u1.py" in fidelity
    assert "test_company_settings_br20_c1.py" in fidelity
    assert "test_reliability_cache_r1.py" in fidelity
    assert "test_stage19_fidelity_d1.py" in fidelity
    assert "test_stage19_exit_h19x.py" in fidelity or "H19x" in fidelity
    assert "DR_LOGICAL_BACKUP_RUNBOOK.md" in fidelity
    assert "ADR-043" in fidelity or "ADR_043" in fidelity
    assert "ADR-044" in fidelity or "exit met" in fidelity.lower()
    assert "H19x" in fidelity
    assert "Kubernetes" in fidelity or "WAL" in fidelity or "1000-VU" in fidelity
    assert "WYSIWYG" in fidelity or "cursor pagination" in fidelity.lower()

    plan = _read("docs/STAGE_19_PLAN.md")
    assert "STAGE_19_FIDELITY.md" in plan
    for ws in ("K1", "P1", "S1", "A1", "U1", "C1", "R1", "D1", "H19x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}**" in ln][0]
        assert "COMPLETE" in line, ws
    assert "Closed" in plan or "exit met" in plan.lower() or "ADR-044" in plan
    assert "STAGE_19_EXIT_CRITERIA.md" in plan
    assert "ADR-044" in plan or "ADR_044" in plan
    assert "ADR-043" in plan or "ADR_043" in plan


def test_stage19_br_18_20_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 19 K1" in br
    assert "Stage 19 P1" in br
    assert "Stage 19 S1" in br
    assert "Stage 19 A1" in br
    assert "Stage 19 U1" in br
    assert "Stage 19 C1" in br
    assert "Stage 19 D1" in br
    assert "STAGE_19_FIDELITY.md" in br

    s181 = br.split("#### BR-18.1 Authentication API")[1].split("#### BR-18.2")[0]
    assert "[x] OAuth2 / JWT token generation" in s181
    assert "[x] Token refresh endpoint" in s181
    assert "[x] API key support" in s181
    assert "[x] Rate limiting per tenant" in s181

    s186 = br.split("#### BR-18.6 API Standards")[1].split("### 4.19")[0]
    assert "[x] RESTful design" in s186
    assert "[x] Pagination for list endpoints" in s186
    assert "[x] Versioning (/api/v1/)" in s186
    assert "[x] OpenAPI/Swagger" in s186
    assert "[x] Webhook support" in s186

    s191 = br.split("#### BR-19.1 Authentication")[1].split("#### BR-19.2")[0]
    assert "[x] Email/password login with bcrypt hashing" in s191
    assert "[x] Account lockout after 5 failed attempts" in s191

    s193 = br.split("#### BR-19.3 Session Management")[1].split("### 4.20")[0]
    assert "[x] Refresh token rotation" in s193
    assert "[x] Auto-logout on inactivity" in s193

    s201 = br.split("#### BR-20.1 Company Information")[1].split("#### BR-20.2")[0]
    assert "[x] Edit legal name, address, contact, tax ID" in s201
    assert "[x] Upload company logo" in s201

    s204 = br.split("#### BR-20.4 Numbering & Templates")[1].split("### 4.21")[0]
    assert "[x] Configure invoice numbering prefix and series" in s204
    assert "[x] Header/footer customization with company branding" in s204


def test_stage19_security_api_launch_checklist():
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 19 K1" in sec
    assert "Stage 19 U1" in sec
    assert "test_auth_api_fidelity_k1.py" in sec
    assert "test_auth_session_br19_u1.py" in sec
    assert "STAGE_19_FIDELITY.md" in sec or "Stage 19 D1" in sec
    assert "8 characters" in sec
    assert "30-minute lockout" in sec

    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 19 K1" in api
    assert "Stage 19 P1" in api
    assert "Stage 19 S1" in api
    assert "Stage 19 A1" in api
    assert "Stage 19 D1" in api or "STAGE_19_FIDELITY.md" in api
    assert "test_api_standards_a1.py" in api

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_auth_api_fidelity_k1.py" in launch
    assert "test_products_customers_api_p1.py" in launch
    assert "test_sales_purchases_api_s1.py" in launch
    assert "test_api_standards_a1.py" in launch
    assert "test_auth_session_br19_u1.py" in launch
    assert "test_company_settings_br20_c1.py" in launch
    assert "test_reliability_cache_r1.py" in launch
    assert "test_stage19_fidelity_d1.py" in launch
    assert "STAGE_19_FIDELITY.md" in launch
    assert "test_stage19_exit_h19x.py" in launch
    section5 = launch.split("## 5. Reliability & cache")[1].split("## 6.")[0]
    assert "[x] Dashboard / catalog cache soft-fails if Redis blips" in section5
    assert "[x] Permissions cache invalidates after role / record_scope change" in section5
    assert "[x] Celery beat schedules include:" in section5
    assert "[x] Admin `GET /jobs` + manual `POST /jobs/{name}/run`" in section5


def test_stage19_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_19_FIDELITY.md" in pr
    assert "test_stage19_fidelity_d1.py" in pr
    assert "test_auth_api_fidelity_k1.py" in pr
    assert "test_auth_session_br19_u1.py" in pr
    assert "test_company_settings_br20_c1.py" in pr
    assert "test_reliability_cache_r1.py" in pr
    assert "STAGE_19_EXIT_CRITERIA.md" in pr or "ADR-044" in pr or "ADR_044" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_19_FIDELITY.md" in roadmap
    assert "Stage 19 D1" in roadmap
    assert "ADR_043_STAGE19_OPEN.md" in roadmap
    assert "STAGE_19_PLAN.md" in roadmap
    assert "STAGE_19_EXIT_CRITERIA.md" in roadmap
    assert "ADR_044_STAGE19_FREEZE.md" in roadmap
    assert "Stage 19 exit" in roadmap
