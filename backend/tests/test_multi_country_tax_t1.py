"""Stage 60 T1 — multi-country tax honesty (not live e-file / tax engine Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "multi-country-tax.json"
GEO = ROOT / "ops" / "mvp" / "geographic-expansion.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage60_t1_multi_country_tax.json"

REQUIRED_IDS = {
    "mct-product-overview",
    "mct-geographic",
    "mct-billing-deferred",
    "mct-compliance-q",
    "mct-manufacturing-adjacency",
    "mct-ecommerce-adjacency",
    "mct-roadmap-backlog",
    "mct-plan-honesty",
    "mct-engine-remaining",
    "mct-efile-remaining",
}
REQUIRED_CATEGORIES = {"tax", "compliance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_multi_country_tax_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "60"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["multi_country_tax_engine_claimed"] is False
    assert mapping["tax_efile_portal_live_claimed"] is False
    assert mapping["gst_vat_sales_tax_compliance_live"] is False
    assert mapping["multi_country_tax_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/MULTI_COUNTRY_TAX_MVP.md"
    assert "stage60_t1_multi_country_tax.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "mct-engine-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "mct-efile-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "tax" in d.lower()
        or "gst" in d.lower()
        or "vat" in d.lower()
        or "e-file" in d.lower()
        or "efile" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["geographic_expansion"],
        mapping["geographic_expansion_doc"],
        mapping["billing_deferred_honesty"],
        mapping["billing_deferred_honesty_doc"],
        mapping["compliance_questionnaire"],
        mapping["compliance_questionnaire_doc"],
        mapping["advanced_manufacturing"],
        mapping["advanced_manufacturing_doc"],
        mapping["ecommerce_integration"],
        mapping["ecommerce_integration_doc"],
        mapping["development_roadmap"],
        mapping["stage60_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_multi_country_tax_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    assert mapping["multi_country_tax_engine_claimed"] is False
    assert mapping["tax_efile_portal_live_claimed"] is False
    for key in (
        "multi_market_expansion_claimed",
        "international_localization_claimed",
        "geographic_expansion_program_live",
    ):
        if key in geo:
            assert geo[key] is False
    for key in (
        "billing_complete_claimed",
        "payment_provider_claimed",
        "checkout_success_claimed",
    ):
        if key in billing:
            assert billing[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Multi-country tax" in po
        or "GST" in po
        or "VAT" in po
        or "Sales Tax" in po
    )


def test_multi_country_tax_doc_and_readme():
    doc = _read("docs/MULTI_COUNTRY_TAX_MVP.md")
    assert "Stage 60 T1" in doc
    assert "test_multi_country_tax_t1.py" in doc
    assert "multi-country-tax.json" in doc
    assert "stage60_t1_multi_country_tax.json" in doc
    assert "multi_country_tax_engine_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "tax" in doc.lower() or "gst" in doc.lower() or "vat" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 60 T1" in readme
    assert "MULTI_COUNTRY_TAX_MVP.md" in readme
    assert "multi-country-tax.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_60_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_multi_country_tax_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H60x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_multi_country_tax_t1.py" in launch
    assert "Stage 60 T1" in launch
    assert "MULTI_COUNTRY_TAX_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 60 T1" in roadmap
    assert "test_multi_country_tax_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 60 T1" in pr
    assert "test_multi_country_tax_t1.py" in pr or "MULTI_COUNTRY_TAX_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "60",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/MULTI_COUNTRY_TAX_MVP.md",
        "register": "ops/mvp/multi-country-tax.json",
        "packaging_complete": True,
        "multi_country_tax_engine_claimed": False,
        "tax_efile_portal_live_claimed": False,
        "gst_vat_sales_tax_compliance_live": False,
        "multi_country_tax_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["multi_country_tax_engine_claimed"] is False
    assert loaded["tax_efile_portal_live_claimed"] is False
    assert loaded["step_count"] >= 10
