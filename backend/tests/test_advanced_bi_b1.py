"""Stage 64 B1 — Advanced BI honesty (not live custom analytics / BI Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "advanced-bi.json"
ADDON = ROOT / "ops" / "mvp" / "addon-services.json"
METRICS = ROOT / "ops" / "mvp" / "business-metrics.json"
SUCCESS = ROOT / "ops" / "mvp" / "success-metrics.json"
AI_METRICS = ROOT / "ops" / "mvp" / "ai-metrics.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage64_b1_advanced_bi.json"

REQUIRED_IDS = {
    "abi-product-overview",
    "abi-br-report-builder",
    "abi-addon-custom-report",
    "abi-business-metrics",
    "abi-success-metrics",
    "abi-ai-metrics",
    "abi-stage23-reports",
    "abi-plan-honesty",
    "abi-advanced-bi-remaining",
    "abi-report-builder-remaining",
}
REQUIRED_CATEGORIES = {"analytics", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_advanced_bi_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "64"
    assert mapping["workstream"] == "B1"
    assert mapping["packaging_complete"] is True
    assert mapping["advanced_bi_live_claimed"] is False
    assert mapping["custom_analytics_live_claimed"] is False
    assert mapping["custom_report_builder_live"] is False
    assert mapping["advanced_bi_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ADVANCED_BI_MVP.md"
    assert "stage64_b1_advanced_bi.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "abi-advanced-bi-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "abi-report-builder-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "bi" in d.lower()
        or "analytics" in d.lower()
        or "report" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["business_requirements"],
        mapping["addon_services"],
        mapping["addon_services_doc"],
        mapping["business_metrics"],
        mapping["business_metrics_doc"],
        mapping["success_metrics"],
        mapping["success_metrics_doc"],
        mapping["ai_metrics"],
        mapping["ai_metrics_doc"],
        mapping["stage23_fidelity"],
        mapping["development_roadmap"],
        mapping["stage64_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_advanced_bi_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    addon = json.loads(ADDON.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    success = json.loads(SUCCESS.read_text(encoding="utf-8"))
    ai_metrics = json.loads(AI_METRICS.read_text(encoding="utf-8"))
    assert mapping["advanced_bi_live_claimed"] is False
    assert mapping["custom_analytics_live_claimed"] is False
    for key in ("addon_catalog_live", "addon_billing_claimed", "premium_ai_addon_claimed"):
        if key in addon:
            assert addon[key] is False
    for key in ("mrr_measured_claimed", "paying_customers_measured_claimed", "business_metrics_program_live"):
        if key in metrics:
            assert metrics[key] is False
    for key in ("mau_measured_claimed", "nps_measured_claimed", "success_metrics_program_live"):
        if key in success:
            assert success[key] is False
    for key in (
        "ai_feature_adoption_measured_claimed",
        "prediction_accuracy_measured_claimed",
        "ai_metrics_program_live",
    ):
        if key in ai_metrics:
            assert ai_metrics[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Advanced BI" in po or "custom analytics" in po.lower()
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Advanced BI" in br or "custom report" in br.lower()


def test_advanced_bi_doc_and_readme():
    doc = _read("docs/ADVANCED_BI_MVP.md")
    assert "Stage 64 B1" in doc
    assert "test_advanced_bi_b1.py" in doc
    assert "advanced-bi.json" in doc
    assert "stage64_b1_advanced_bi.json" in doc
    assert "advanced_bi_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "bi" in doc.lower() or "analytics" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 64 B1" in readme
    assert "ADVANCED_BI_MVP.md" in readme
    assert "advanced-bi.json" in readme


def test_b1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_64_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_advanced_bi_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "F1 next" in plan
        or "F1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H64x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_advanced_bi_b1.py" in launch
    assert "Stage 64 B1" in launch
    assert "ADVANCED_BI_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 64 B1" in roadmap
    assert "test_advanced_bi_b1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 64 B1" in pr
    assert "test_advanced_bi_b1.py" in pr or "ADVANCED_BI_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "64",
        "workstream": "B1",
        "passed": True,
        "doc": "docs/ADVANCED_BI_MVP.md",
        "register": "ops/mvp/advanced-bi.json",
        "packaging_complete": True,
        "advanced_bi_live_claimed": False,
        "custom_analytics_live_claimed": False,
        "custom_report_builder_live": False,
        "advanced_bi_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["advanced_bi_live_claimed"] is False
    assert loaded["custom_analytics_live_claimed"] is False
    assert loaded["step_count"] >= 10
