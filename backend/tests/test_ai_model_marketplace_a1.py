"""Stage 62 A1 — AI model marketplace honesty (not live industry-prediction marketplace Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-model-marketplace.json"
AI_METRICS = ROOT / "ops" / "mvp" / "ai-metrics.json"
MARKETPLACE = ROOT / "ops" / "mvp" / "marketplace-presence.json"
PROVIDER = ROOT / "ops" / "mvp" / "ai-provider-boundary.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage62_a1_ai_model_marketplace.json"

REQUIRED_IDS = {
    "aim-product-overview",
    "aim-ai-metrics",
    "aim-provider-boundary",
    "aim-use-disclosure",
    "aim-marketplace-presence",
    "aim-addon-services",
    "aim-iot-adjacency",
    "aim-plan-honesty",
    "aim-prediction-marketplace-remaining",
    "aim-marketplace-program-remaining",
}
REQUIRED_CATEGORIES = {"ai", "marketplace", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ai_model_marketplace_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "62"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["ai_model_marketplace_live_claimed"] is False
    assert mapping["industry_prediction_marketplace_claimed"] is False
    assert mapping["model_vendor_catalog_live"] is False
    assert mapping["ai_marketplace_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/AI_MODEL_MARKETPLACE_MVP.md"
    assert "stage62_a1_ai_model_marketplace.json" in mapping["evidence_artifact"]
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
    assert any(
        s["id"] == "aim-prediction-marketplace-remaining" and s["status"] == "remaining"
        for s in steps
    )
    assert any(
        s["id"] == "aim-marketplace-program-remaining" and s["status"] == "remaining"
        for s in steps
    )
    assert any(
        "marketplace" in d.lower()
        or "prediction" in d.lower()
        or "model" in d.lower()
        or "ai" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["ai_metrics"],
        mapping["ai_metrics_doc"],
        mapping["ai_provider_boundary"],
        mapping["ai_provider_boundary_doc"],
        mapping["ai_use_disclosure"],
        mapping["ai_use_disclosure_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["addon_services"],
        mapping["addon_services_doc"],
        mapping["iot_integration"],
        mapping["iot_integration_doc"],
        mapping["development_roadmap"],
        mapping["stage62_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ai_model_marketplace_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    ai_metrics = json.loads(AI_METRICS.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    provider = json.loads(PROVIDER.read_text(encoding="utf-8"))
    assert mapping["ai_model_marketplace_live_claimed"] is False
    assert mapping["industry_prediction_marketplace_claimed"] is False
    for key in (
        "ai_feature_adoption_measured_claimed",
        "prediction_accuracy_measured_claimed",
        "ai_metrics_program_live",
    ):
        if key in ai_metrics:
            assert ai_metrics[key] is False
    for key in (
        "marketplace_listing_live",
        "plugin_marketplace_live",
        "marketplace_revenue_share_claimed",
    ):
        if key in marketplace:
            assert marketplace[key] is False
    for key in ("external_llm_claimed", "prophet_claimed"):
        if key in provider:
            assert provider[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "AI model marketplace" in po
        or "model marketplace" in po.lower()
        or "industry-specific predictions" in po.lower()
    )


def test_ai_model_marketplace_doc_and_readme():
    doc = _read("docs/AI_MODEL_MARKETPLACE_MVP.md")
    assert "Stage 62 A1" in doc
    assert "test_ai_model_marketplace_a1.py" in doc
    assert "ai-model-marketplace.json" in doc
    assert "stage62_a1_ai_model_marketplace.json" in doc
    assert "ai_model_marketplace_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "marketplace" in doc.lower() or "prediction" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 62 A1" in readme
    assert "AI_MODEL_MARKETPLACE_MVP.md" in readme
    assert "ai-model-marketplace.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_62_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_ai_model_marketplace_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H62x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_model_marketplace_a1.py" in launch
    assert "Stage 62 A1" in launch
    assert "AI_MODEL_MARKETPLACE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 62 A1" in roadmap
    assert "test_ai_model_marketplace_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 62 A1" in pr
    assert "test_ai_model_marketplace_a1.py" in pr or "AI_MODEL_MARKETPLACE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "62",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/AI_MODEL_MARKETPLACE_MVP.md",
        "register": "ops/mvp/ai-model-marketplace.json",
        "packaging_complete": True,
        "ai_model_marketplace_live_claimed": False,
        "industry_prediction_marketplace_claimed": False,
        "model_vendor_catalog_live": False,
        "ai_marketplace_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["ai_model_marketplace_live_claimed"] is False
    assert loaded["industry_prediction_marketplace_claimed"] is False
    assert loaded["step_count"] >= 10
