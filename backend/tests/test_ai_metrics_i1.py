"""Stage 58 I1 — AI metrics honesty (not measured AI adoption / accuracy / chat resolution Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ai-metrics.json"
PROVIDER = ROOT / "ops" / "mvp" / "ai-provider-boundary.json"
DISCLOSURE = ROOT / "ops" / "mvp" / "ai-use-disclosure.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage58_i1_ai_metrics.json"

REQUIRED_IDS = {
    "am-product-overview",
    "am-provider-boundary",
    "am-use-disclosure",
    "am-business-metrics",
    "am-success-metrics",
    "am-stage42-fidelity",
    "am-roadmap-backlog",
    "am-plan-honesty",
    "am-adoption-remaining",
    "am-accuracy-remaining",
}
REQUIRED_CATEGORIES = {"ai", "metrics", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ai_metrics_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "58"
    assert mapping["workstream"] == "I1"
    assert mapping["packaging_complete"] is True
    assert mapping["ai_feature_adoption_measured_claimed"] is False
    assert mapping["prediction_accuracy_measured_claimed"] is False
    assert mapping["chat_resolution_measured_claimed"] is False
    assert mapping["ai_metrics_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/AI_METRICS_MVP.md"
    assert "stage58_i1_ai_metrics.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "am-adoption-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "am-accuracy-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "ai" in d.lower()
        or "prediction" in d.lower()
        or "chat" in d.lower()
        or "adoption" in d.lower()
        or "accuracy" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["ai_provider_boundary"],
        mapping["ai_provider_boundary_doc"],
        mapping["ai_use_disclosure"],
        mapping["ai_use_disclosure_doc"],
        mapping["business_metrics"],
        mapping["business_metrics_doc"],
        mapping["success_metrics"],
        mapping["success_metrics_doc"],
        mapping["stage42_fidelity"],
        mapping["stage20_fidelity"],
        mapping["development_roadmap"],
        mapping["stage58_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ai_metrics_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    provider = json.loads(PROVIDER.read_text(encoding="utf-8"))
    disclosure = json.loads(DISCLOSURE.read_text(encoding="utf-8"))
    assert mapping["ai_feature_adoption_measured_claimed"] is False
    assert mapping["prediction_accuracy_measured_claimed"] is False
    for key in ("external_llm_claimed", "prophet_claimed"):
        if key in provider:
            assert provider[key] is False
    for key in ("ai_certification_claimed", "external_llm_claimed", "ai_advice_binding_claimed"):
        if key in disclosure:
            assert disclosure[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "AI Feature Adoption" in po
        or "Prediction Accuracy" in po
        or "Chat Assistant" in po
        or "AI Metrics" in po
    )


def test_ai_metrics_doc_and_readme():
    doc = _read("docs/AI_METRICS_MVP.md")
    assert "Stage 58 I1" in doc
    assert "test_ai_metrics_i1.py" in doc
    assert "ai-metrics.json" in doc
    assert "stage58_i1_ai_metrics.json" in doc
    assert "ai_feature_adoption_measured_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "ai" in doc.lower() or "prediction" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 58 I1" in readme
    assert "AI_METRICS_MVP.md" in readme
    assert "ai-metrics.json" in readme


def test_i1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_58_PLAN.md")
    i1_line = [ln for ln in plan.splitlines() if "| **I1** |" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_ai_metrics_i1.py" in plan
    assert (
        "I1 next" in plan
        or "I1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H58x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ai_metrics_i1.py" in launch
    assert "Stage 58 I1" in launch
    assert "AI_METRICS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 58 I1" in roadmap
    assert "test_ai_metrics_i1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 58 I1" in pr
    assert "test_ai_metrics_i1.py" in pr or "AI_METRICS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "58",
        "workstream": "I1",
        "passed": True,
        "doc": "docs/AI_METRICS_MVP.md",
        "register": "ops/mvp/ai-metrics.json",
        "packaging_complete": True,
        "ai_feature_adoption_measured_claimed": False,
        "prediction_accuracy_measured_claimed": False,
        "chat_resolution_measured_claimed": False,
        "ai_metrics_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["ai_feature_adoption_measured_claimed"] is False
    assert loaded["prediction_accuracy_measured_claimed"] is False
    assert loaded["step_count"] >= 10
