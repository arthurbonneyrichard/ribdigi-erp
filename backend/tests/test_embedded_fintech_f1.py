"""Stage 61 F1 — embedded fintech honesty (not live lending / invoice financing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "embedded-fintech.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
PRICING = ROOT / "ops" / "mvp" / "pricing-transparency.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage61_f1_embedded_fintech.json"

REQUIRED_IDS = {
    "ef-product-overview",
    "ef-billing-deferred",
    "ef-pricing",
    "ef-subscription",
    "ef-unit-economics",
    "ef-tax-adjacency",
    "ef-cancellation",
    "ef-plan-honesty",
    "ef-lending-remaining",
    "ef-invoice-financing-remaining",
}
REQUIRED_CATEGORIES = {"fintech", "commercial", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_embedded_fintech_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "61"
    assert mapping["workstream"] == "F1"
    assert mapping["packaging_complete"] is True
    assert mapping["lending_product_live_claimed"] is False
    assert mapping["invoice_financing_live_claimed"] is False
    assert mapping["embedded_fintech_program_live"] is False
    assert mapping["fintech_marketplace_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/EMBEDDED_FINTECH_MVP.md"
    assert "stage61_f1_embedded_fintech.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    ids = {s["id"] for s in steps}
    assert REQUIRED_IDS.issubset(ids)
    cats = {s["category"] for s in steps}
    assert REQUIRED_CATEGORIES.issubset(cats)
    for step in steps:
        assert step["done"] is False
        assert step["status"] in ("packaged", "remaining")
        assert step["title"]
        assert step["source"]
        assert isinstance(step["pack_refs"], list) and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "ef-lending-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ef-invoice-financing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "lend" in d.lower()
        or "financ" in d.lower()
        or "fintech" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred_honesty"],
        mapping["billing_deferred_honesty_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["subscription_renewal"],
        mapping["subscription_renewal_doc"],
        mapping["unit_economics_positioning"],
        mapping["unit_economics_positioning_doc"],
        mapping["multi_country_tax"],
        mapping["multi_country_tax_doc"],
        mapping["cancellation_churn"],
        mapping["cancellation_churn_doc"],
        mapping["development_roadmap"],
        mapping["stage61_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_embedded_fintech_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    assert mapping["lending_product_live_claimed"] is False
    assert mapping["invoice_financing_live_claimed"] is False
    for key in (
        "billing_complete_claimed",
        "payment_provider_claimed",
        "checkout_success_claimed",
    ):
        if key in billing:
            assert billing[key] is False
    for key in (
        "public_pricing_portal_live",
        "binding_list_prices_claimed",
        "checkout_pricing_live",
        "pricing_transparency_program_live",
    ):
        if key in pricing:
            assert pricing[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "fintech" in po.lower()
        or "lending" in po.lower()
        or "invoice financing" in po.lower()
    )


def test_embedded_fintech_doc_and_readme():
    doc = _read("docs/EMBEDDED_FINTECH_MVP.md")
    assert "Stage 61 F1" in doc
    assert "test_embedded_fintech_f1.py" in doc
    assert "embedded-fintech.json" in doc
    assert "stage61_f1_embedded_fintech.json" in doc
    assert "lending_product_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "fintech" in doc.lower() or "lending" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 61 F1" in readme
    assert "EMBEDDED_FINTECH_MVP.md" in readme
    assert "embedded-fintech.json" in readme


def test_f1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_61_PLAN.md")
    f1_line = [ln for ln in plan.splitlines() if "| **F1** |" in ln][0]
    assert "COMPLETE" in f1_line
    assert "test_embedded_fintech_f1.py" in plan
    assert (
        "F1 next" in plan
        or "F1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H61x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_embedded_fintech_f1.py" in launch
    assert "Stage 61 F1" in launch
    assert "EMBEDDED_FINTECH_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 61 F1" in roadmap
    assert "test_embedded_fintech_f1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 61 F1" in pr
    assert "test_embedded_fintech_f1.py" in pr or "EMBEDDED_FINTECH_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "61",
        "workstream": "F1",
        "passed": True,
        "doc": "docs/EMBEDDED_FINTECH_MVP.md",
        "register": "ops/mvp/embedded-fintech.json",
        "packaging_complete": True,
        "lending_product_live_claimed": False,
        "invoice_financing_live_claimed": False,
        "embedded_fintech_program_live": False,
        "fintech_marketplace_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["lending_product_live_claimed"] is False
    assert loaded["invoice_financing_live_claimed"] is False
    assert loaded["step_count"] >= 10
