"""Stage 25 U1: AI UI fidelity — purchases, cross-domain, document analyze panels."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_PAGE = ROOT / "frontend" / "app" / "ai" / "page.tsx"


def test_ai_page_wires_purchases_cross_domain_and_documents():
    text = AI_PAGE.read_text(encoding="utf-8")
    assert "/ai/purchases/analysis" in text
    assert "loadPurchasesAnalysis" in text
    assert "Purchases analysis" in text
    assert "Refresh purchases analysis" in text

    assert "/ai/cross-domain/analysis" in text
    assert "loadCrossDomainAnalysis" in text
    assert "Cross-domain analysis" in text
    assert "Refresh cross-domain analysis" in text

    assert "/ai/documents/analyze" in text
    assert "analyzeDocument" in text
    assert "Document analyze" in text
    assert "document_type" in text

    # Existing panels remain (no rewrite of sales/expense stack)
    assert "/ai/sales/analysis" in text
    assert "/ai/expenses/analysis" in text
    assert "/ai/insights" in text


def test_u1_plan_and_docs_cite_stage25():
    plan = (ROOT / "docs" / "STAGE_25_PLAN.md").read_text(encoding="utf-8")
    u1_line = [ln for ln in plan.splitlines() if "| **U1** |" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_ai_ui_fidelity_u1.py" in plan
    assert (
        "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H25x next" in plan
    )

    manual = (ROOT / "docs" / "USER_MANUAL.md").read_text(encoding="utf-8")
    assert "Stage 25 U1" in manual or "/ai/purchases/analysis" in manual
    assert "documents/analyze" in manual or "Document analyze" in manual

    api = (ROOT / "docs" / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stage 25 U1" in api or "frontend/app/ai/page.tsx" in api

    launch = (ROOT / "docs" / "LAUNCH_CHECKLIST.md").read_text(encoding="utf-8")
    assert "test_ai_ui_fidelity_u1.py" in launch

    roadmap = (ROOT / "docs" / "DEVELOPMENT_ROADMAP.md").read_text(encoding="utf-8")
    assert "Stage 25 U1" in roadmap
    assert "test_ai_ui_fidelity_u1.py" in roadmap
