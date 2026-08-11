"""Stage 59 C1 — CRM commercial honesty (not live CRM module / segmentation Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "crm-commercial.json"
ECOMMERCE = ROOT / "ops" / "mvp" / "ecommerce-integration.json"
SALES = ROOT / "ops" / "mvp" / "direct-sales.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage59_c1_crm_commercial.json"

REQUIRED_IDS = {
    "crm-product-overview",
    "crm-ecommerce-adjacency",
    "crm-direct-sales",
    "crm-digital-marketing",
    "crm-partner-industry",
    "crm-referral",
    "crm-roadmap-backlog",
    "crm-plan-honesty",
    "crm-module-remaining",
    "crm-segmentation-remaining",
}
REQUIRED_CATEGORIES = {"crm", "channel", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_crm_commercial_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "59"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["crm_module_live_claimed"] is False
    assert mapping["customer_segmentation_live_claimed"] is False
    assert mapping["crm_pipeline_program_live"] is False
    assert mapping["crm_commercial_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CRM_COMMERCIAL_MVP.md"
    assert "stage59_c1_crm_commercial.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "crm-module-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "crm-segmentation-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "crm" in d.lower()
        or "segmentation" in d.lower()
        or "pipeline" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["ecommerce_integration"],
        mapping["ecommerce_integration_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["referral_program"],
        mapping["referral_program_doc"],
        mapping["development_roadmap"],
        mapping["stage59_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_crm_commercial_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    ecommerce = json.loads(ECOMMERCE.read_text(encoding="utf-8"))
    sales = json.loads(SALES.read_text(encoding="utf-8"))
    assert mapping["crm_module_live_claimed"] is False
    assert mapping["customer_segmentation_live_claimed"] is False
    for key in (
        "shopify_connector_live_claimed",
        "woocommerce_connector_live_claimed",
        "ecommerce_integration_program_live",
    ):
        if key in ecommerce:
            assert ecommerce[key] is False
    for key in (
        "inside_sales_team_live",
        "enterprise_pipeline_claimed",
        "direct_sales_program_live",
    ):
        if key in sales:
            assert sales[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "CRM" in po or "segmentation" in po.lower()


def test_crm_commercial_doc_and_readme():
    doc = _read("docs/CRM_COMMERCIAL_MVP.md")
    assert "Stage 59 C1" in doc
    assert "test_crm_commercial_c1.py" in doc
    assert "crm-commercial.json" in doc
    assert "stage59_c1_crm_commercial.json" in doc
    assert "crm_module_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "crm" in doc.lower() or "segmentation" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 59 C1" in readme
    assert "CRM_COMMERCIAL_MVP.md" in readme
    assert "crm-commercial.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_59_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_crm_commercial_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H59x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_crm_commercial_c1.py" in launch
    assert "Stage 59 C1" in launch
    assert "CRM_COMMERCIAL_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 59 C1" in roadmap
    assert "test_crm_commercial_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 59 C1" in pr
    assert "test_crm_commercial_c1.py" in pr or "CRM_COMMERCIAL_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "59",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/CRM_COMMERCIAL_MVP.md",
        "register": "ops/mvp/crm-commercial.json",
        "packaging_complete": True,
        "crm_module_live_claimed": False,
        "customer_segmentation_live_claimed": False,
        "crm_pipeline_program_live": False,
        "crm_commercial_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["crm_module_live_claimed"] is False
    assert loaded["customer_segmentation_live_claimed"] is False
    assert loaded["step_count"] >= 10
