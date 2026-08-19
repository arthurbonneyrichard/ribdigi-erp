"""Stage 60 M1 — advanced manufacturing honesty (not live MRP / scheduling Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "advanced-manufacturing.json"
PURCHASE = ROOT / "ops" / "mvp" / "e2e-purchase-stock.json"
INDUSTRY = ROOT / "ops" / "mvp" / "industry-partnerships.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage60_m1_advanced_manufacturing.json"

REQUIRED_IDS = {
    "am-product-overview",
    "am-purchase-stock",
    "am-industry",
    "am-white-label",
    "am-onboarding",
    "am-channel-adjacency",
    "am-roadmap-backlog",
    "am-plan-honesty",
    "am-mrp-remaining",
    "am-scheduling-remaining",
}
REQUIRED_CATEGORIES = {"manufacturing", "ops", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_advanced_manufacturing_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "60"
    assert mapping["workstream"] == "M1"
    assert mapping["packaging_complete"] is True
    assert mapping["mrp_module_live_claimed"] is False
    assert mapping["production_scheduling_live_claimed"] is False
    assert mapping["bom_mrp_program_live"] is False
    assert mapping["advanced_manufacturing_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ADVANCED_MANUFACTURING_MVP.md"
    assert "stage60_m1_advanced_manufacturing.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "am-mrp-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "am-scheduling-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "mrp" in d.lower()
        or "manufactur" in d.lower()
        or "schedul" in d.lower()
        or "bom" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["e2e_purchase_stock"],
        mapping["e2e_purchase_stock_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["white_label_licensing"],
        mapping["white_label_licensing_doc"],
        mapping["implementation_onboarding"],
        mapping["implementation_onboarding_doc"],
        mapping["ecommerce_integration"],
        mapping["ecommerce_integration_doc"],
        mapping["crm_commercial"],
        mapping["crm_commercial_doc"],
        mapping["development_roadmap"],
        mapping["stage60_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_advanced_manufacturing_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    purchase = json.loads(PURCHASE.read_text(encoding="utf-8"))
    industry = json.loads(INDUSTRY.read_text(encoding="utf-8"))
    assert mapping["mrp_module_live_claimed"] is False
    assert mapping["production_scheduling_live_claimed"] is False
    for key in ("purchase_stock_e2e_program_live", "live_purchase_stock_claimed"):
        if key in purchase:
            assert purchase[key] is False
    for key in (
        "industry_partnership_program_live",
        "signed_association_deals_claimed",
        "industry_partnerships_program_live",
    ):
        if key in industry:
            assert industry[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Manufacturing" in po
        or "MRP" in po
        or "production scheduling" in po.lower()
    )


def test_advanced_manufacturing_doc_and_readme():
    doc = _read("docs/ADVANCED_MANUFACTURING_MVP.md")
    assert "Stage 60 M1" in doc
    assert "test_advanced_manufacturing_m1.py" in doc
    assert "advanced-manufacturing.json" in doc
    assert "stage60_m1_advanced_manufacturing.json" in doc
    assert "mrp_module_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "mrp" in doc.lower() or "manufactur" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 60 M1" in readme
    assert "ADVANCED_MANUFACTURING_MVP.md" in readme
    assert "advanced-manufacturing.json" in readme


def test_m1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_60_PLAN.md")
    m1_line = [ln for ln in plan.splitlines() if "| **M1** |" in ln][0]
    assert "COMPLETE" in m1_line
    assert "test_advanced_manufacturing_m1.py" in plan
    assert (
        "M1 next" in plan
        or "M1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H60x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_advanced_manufacturing_m1.py" in launch
    assert "Stage 60 M1" in launch
    assert "ADVANCED_MANUFACTURING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 60 M1" in roadmap
    assert "test_advanced_manufacturing_m1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 60 M1" in pr
    assert "test_advanced_manufacturing_m1.py" in pr or "ADVANCED_MANUFACTURING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "60",
        "workstream": "M1",
        "passed": True,
        "doc": "docs/ADVANCED_MANUFACTURING_MVP.md",
        "register": "ops/mvp/advanced-manufacturing.json",
        "packaging_complete": True,
        "mrp_module_live_claimed": False,
        "production_scheduling_live_claimed": False,
        "bom_mrp_program_live": False,
        "advanced_manufacturing_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["mrp_module_live_claimed"] is False
    assert loaded["production_scheduling_live_claimed"] is False
    assert loaded["step_count"] >= 10
