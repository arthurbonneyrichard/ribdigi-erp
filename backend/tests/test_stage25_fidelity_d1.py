"""Stage 25 D1 — documentation fidelity for actuals → AI → insights (BR-21)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage25_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_25_FIDELITY.md")
    assert "BR-21" in fidelity or "purchases" in fidelity.lower()
    assert "test_ai_purchases_analysis_p1.py" in fidelity
    assert "test_ai_cross_domain_x1.py" in fidelity
    assert "test_ai_business_insights_b1.py" in fidelity
    assert "test_ai_ui_fidelity_u1.py" in fidelity
    assert "test_stage25_fidelity_d1.py" in fidelity
    assert "ADR-055" in fidelity or "ADR_055" in fidelity
    assert "Actual Inventory" in fidelity or "four actual" in fidelity.lower() or "Purchases" in fidelity
    assert "WAL" in fidelity or "PITR" in fidelity or "Prophet" in fidelity or "LLM" in fidelity
    assert "H25x" in fidelity

    plan = _read("docs/STAGE_25_PLAN.md")
    assert "STAGE_25_FIDELITY.md" in plan
    for ws in ("P1", "X1", "B1", "U1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "H25x" in plan and "PENDING" in plan
    assert "ADR-055" in plan or "ADR_055" in plan
    assert "D1 complete" in plan or "H25x next" in plan


def test_stage25_br_21_and_gate_cites():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 25 P1" in br
    assert "Stage 25 X1" in br
    assert "Stage 25 B1" in br
    assert "Stage 25 D1" in br
    assert "STAGE_25_FIDELITY.md" in br

    s2111 = br.split("#### BR-21.11 AI Purchases Analysis")[1].split("#### BR-21.12")[0]
    assert "[x]" in s2111
    assert "/ai/purchases/analysis" in s2111
    assert "test_ai_purchases_analysis_p1.py" in s2111

    s2112 = br.split("#### BR-21.12 Cross-Domain AI Analysis")[1].split("---")[0]
    assert "[x]" in s2112
    assert "/ai/cross-domain/analysis" in s2112
    assert "test_ai_cross_domain_x1.py" in s2112

    s212 = br.split("#### BR-21.2 AI Dashboard Insight")[1].split("#### BR-21.3")[0]
    assert "Stage 25 B1" in s212
    assert "actuals_covered" in s212 or "domains" in s212


def test_stage25_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 25 D1" in api or "STAGE_25_FIDELITY.md" in api
    assert "test_stage25_fidelity_d1.py" in api or "STAGE_25_FIDELITY.md" in api
    assert "/ai/purchases/analysis" in api
    assert "/ai/cross-domain/analysis" in api
    assert "test_ai_purchases_analysis_p1.py" in api
    assert "test_ai_cross_domain_x1.py" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "Stage 25" in manual or "STAGE_25_FIDELITY" in manual
    assert "/ai/purchases/analysis" in manual
    assert "/ai/cross-domain/analysis" in manual
    assert "STAGE_25_FIDELITY" in manual or "Stage 25 D1" in manual

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_purchases_analysis_p1.py" in launch
    assert "test_ai_cross_domain_x1.py" in launch
    assert "test_ai_business_insights_b1.py" in launch
    assert "test_ai_ui_fidelity_u1.py" in launch
    assert "test_stage25_fidelity_d1.py" in launch
    assert "STAGE_25_FIDELITY.md" in launch


def test_stage25_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_25_FIDELITY.md" in pr
    assert "test_stage25_fidelity_d1.py" in pr
    assert "Stage 25 D1" in pr
    assert "Stage 25 P1" in pr or "test_ai_purchases_analysis_p1.py" in pr
    assert "Stage 25 X1" in pr or "test_ai_cross_domain_x1.py" in pr
    assert "- [x] AI functions use real tenant data" in pr
    assert "- [ ] Monitoring, metrics, logging and alerting complete." in pr
    assert "- [ ] Point-in-time recovery/WAL strategy complete." in pr
    assert "Prophet" in pr or "LLM" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_25_FIDELITY.md" in roadmap
    assert "Stage 25 D1" in roadmap
    assert "ADR_055_STAGE25_OPEN.md" in roadmap
    assert "STAGE_25_PLAN.md" in roadmap
