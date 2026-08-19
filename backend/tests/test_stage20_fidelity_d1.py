"""Stage 20 D1 — documentation fidelity for AI Business Assistant (BR-21)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage20_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_20_FIDELITY.md")
    assert "BR-21" in fidelity
    assert "test_ai_chat_fidelity_c1.py" in fidelity
    assert "test_ai_insights_fidelity_i1.py" in fidelity
    assert "test_ai_inventory_intel_v1.py" in fidelity
    assert "test_ai_low_stock_prediction_l1.py" in fidelity
    assert "test_ai_sales_analysis_s1.py" in fidelity
    assert "test_ai_report_generator_r1.py" in fidelity
    assert "test_ai_customer_security_u1.py" in fidelity
    assert "test_stage20_fidelity_d1.py" in fidelity
    assert "ADR-045" in fidelity or "ADR_045" in fidelity
    assert "Prophet" in fidelity or "LLM" in fidelity or "Kubernetes" in fidelity
    assert "H20x" in fidelity

    plan = _read("docs/STAGE_20_PLAN.md")
    assert "STAGE_20_FIDELITY.md" in plan
    for ws in ("C1", "I1", "V1", "L1", "S1", "R1", "U1", "D1", "H20x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}**" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-045" in plan or "ADR_045" in plan
    assert "ADR-046" in plan or "ADR_046" in plan or "Closed" in plan
    assert "STAGE_20_EXIT_CRITERIA.md" in plan
    assert "test_stage20_exit_h20x.py" in fidelity or "ADR-046" in fidelity or "ADR_046" in fidelity


def test_stage20_br_21_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 20 C1" in br
    assert "Stage 20 I1" in br
    assert "Stage 20 V1" in br
    assert "Stage 20 L1" in br
    assert "Stage 20 S1" in br
    assert "Stage 20 R1" in br
    assert "Stage 20 U1" in br
    assert "Stage 20 D1" in br
    assert "STAGE_20_FIDELITY.md" in br

    s211 = br.split("#### BR-21.1 AI ERP Chat Assistant")[1].split("#### BR-21.2")[0]
    assert "[x] Accept natural language queries" in s211
    assert "[x] Execute commands via chat" in s211
    assert "[x] Context-aware responses based on user role" in s211
    assert "[x] Chat history persistence" in s211

    s212 = br.split("#### BR-21.2 AI Dashboard Insight")[1].split("#### BR-21.3")[0]
    assert "[x] Highlight unusual sales drops or spikes" in s212
    assert "[x] Flag expense anomalies" in s212
    assert "[x] Suggest actions" in s212
    assert "[x] Weekly insight digest email" in s212

    s213 = br.split("#### BR-21.3 Smart Inventory Intelligence")[1].split("#### BR-21.4")[0]
    assert "[x] Demand forecasting per product" in s213
    assert "[x] Optimal reorder quantity" in s213
    assert "[x] Seasonality detection" in s213
    assert "[x] Dead stock identification" in s213

    s214 = br.split("#### BR-21.4 AI Low Stock Prediction")[1].split("#### BR-21.5")[0]
    assert "[x] Predict stockouts 7–14 days in advance" in s214
    assert "[x] Consider sales velocity, seasonality, lead time" in s214
    assert "[x] Confidence score on predictions" in s214
    assert "[x] Auto-generate purchase suggestions" in s214

    s215 = br.split("#### BR-21.5 AI Sales Analysis")[1].split("#### BR-21.6")[0]
    assert "[x] Sales trend forecasting" in s215
    assert "[x] Customer segmentation (RFM analysis)" in s215
    assert "[x] Product affinity analysis" in s215
    assert "[x] Peak hour/day predictions" in s215

    s216 = br.split("#### BR-21.6 AI Expense Analysis")[1].split("#### BR-21.7")[0]
    assert "[x] Expense categorization from receipt OCR" in s216
    assert "[x] Budget variance alerts" in s216
    assert "Stage 20 D1" in s216 or "Stage 10" in s216

    s217 = br.split("#### BR-21.7 AI Report Generator")[1].split("#### BR-21.8")[0]
    assert "[x] Generate reports from text prompts" in s217
    assert "[x] Export generated reports" in s217
    assert "[x] Save report templates for reuse" in s217

    s218 = br.split("#### BR-21.8 AI Document Assistant")[1].split("#### BR-21.9")[0]
    assert "[x] OCR extraction from invoices, receipts" in s218
    assert "[x] Auto-match extracted data to system records" in s218
    assert "[x] Data validation and discrepancy flagging" in s218
    assert "Stage 20 D1" in s218 or "Stage 10" in s218

    s219 = br.split("#### BR-21.9 AI Customer Assistant (Basic)")[1].split("#### BR-21.10")[0]
    assert "[x] Customer churn risk scoring" in s219
    assert "[x] Best customer identification" in s219
    assert "[x] Personalized promotion suggestions" in s219

    s2110 = br.split("#### BR-21.10 AI Security Monitor (Basic)")[1].split("---")[0]
    assert "[x] Detect unusual login patterns" in s2110
    assert "[x] Flag suspicious transaction patterns" in s2110
    assert "[x] Alert admins on potential fraud indicators" in s2110


def test_stage20_api_user_manual_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 20 D1" in api or "STAGE_20_FIDELITY.md" in api
    assert "/ai/chat" in api
    assert "/ai/insights" in api
    assert "/ai/inventory/low-stock-prediction" in api
    assert "/ai/inventory/demand-forecast" in api or "/ai/inventory/predictions" in api
    assert "/ai/sales/analysis" in api
    assert "/ai/reports/generate" in api
    assert "/ai/reports/templates" in api
    assert "/ai/customers/insights" in api
    assert "/ai/security/alerts" in api
    assert "test_stage20_fidelity_d1.py" in api or "STAGE_20_FIDELITY.md" in api

    manual = _read("docs/USER_MANUAL.md")
    assert "AI Business Assistant" in manual
    assert "Stage 20" in manual or "/ai/" in manual
    assert "low stock" in manual.lower() or "stockout" in manual.lower()
    assert "report" in manual.lower()
    assert "security" in manual.lower() or "churn" in manual.lower()

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_chat_fidelity_c1.py" in launch
    assert "test_ai_insights_fidelity_i1.py" in launch
    assert "test_ai_inventory_intel_v1.py" in launch
    assert "test_ai_low_stock_prediction_l1.py" in launch
    assert "test_ai_sales_analysis_s1.py" in launch
    assert "test_ai_report_generator_r1.py" in launch
    assert "test_ai_customer_security_u1.py" in launch
    assert "test_stage20_fidelity_d1.py" in launch
    assert "STAGE_20_FIDELITY.md" in launch


def test_stage20_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_20_FIDELITY.md" in pr
    assert "test_stage20_fidelity_d1.py" in pr
    assert "test_ai_chat_fidelity_c1.py" in pr
    assert "test_ai_customer_security_u1.py" in pr
    assert "Stage 20 D1" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_20_FIDELITY.md" in roadmap
    assert "Stage 20 D1" in roadmap
    assert "ADR_045_STAGE20_OPEN.md" in roadmap
    assert "STAGE_20_PLAN.md" in roadmap
    assert "/ai/customers/insights" in roadmap or "customers/insights" in roadmap
    assert "/ai/reports/templates" in roadmap or "report templates" in roadmap.lower()
