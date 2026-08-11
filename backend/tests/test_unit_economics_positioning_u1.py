"""Stage 55 U1 — unit economics / positioning honesty (not measured CAC/LTV Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "unit-economics-positioning.json"
LICENSING = ROOT / "ops" / "mvp" / "white-label-licensing.json"
CHURN = ROOT / "ops" / "mvp" / "cancellation-churn.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage55_u1_unit_economics_positioning.json"

REQUIRED_IDS = {
    "ue-product-overview",
    "ue-licensing-adjacency",
    "ue-pricing-adjacency",
    "ue-churn-adjacency",
    "ue-marketing-adjacency",
    "ue-billing-deferred",
    "ue-roadmap-backlog",
    "ue-plan-honesty",
    "ue-cac-ltv-remaining",
    "ue-competitive-remaining",
}
REQUIRED_CATEGORIES = {"economics", "positioning", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_unit_economics_positioning_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "55"
    assert mapping["workstream"] == "U1"
    assert mapping["packaging_complete"] is True
    assert mapping["cac_ltv_measured_claimed"] is False
    assert mapping["arpu_payback_measured_claimed"] is False
    assert mapping["competitive_superiority_proven"] is False
    assert mapping["win_loss_analysis_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/UNIT_ECONOMICS_POSITIONING_MVP.md"
    assert "stage55_u1_unit_economics_positioning.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ue-cac-ltv-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ue-competitive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "cac" in d.lower()
        or "ltv" in d.lower()
        or "competitive" in d.lower()
        or "arpu" in d.lower()
        or "win-loss" in d.lower()
        or "win/loss" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["white_label_licensing"],
        mapping["white_label_licensing_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["cancellation_churn"],
        mapping["cancellation_churn_doc"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["development_roadmap"],
        mapping["stage55_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_unit_economics_positioning_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    licensing = json.loads(LICENSING.read_text(encoding="utf-8"))
    churn = json.loads(CHURN.read_text(encoding="utf-8"))
    assert mapping["cac_ltv_measured_claimed"] is False
    assert mapping["competitive_superiority_proven"] is False
    assert licensing.get("white_label_licensing_live") is False
    if "churn_measurement_live" in churn:
        assert churn["churn_measurement_live"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Unit Economics" in po
        or "CAC" in po
        or "LTV" in po
        or "Competitive" in po
        or "Positioning" in po
    )


def test_unit_economics_positioning_doc_and_readme():
    doc = _read("docs/UNIT_ECONOMICS_POSITIONING_MVP.md")
    assert "Stage 55 U1" in doc
    assert "test_unit_economics_positioning_u1.py" in doc
    assert "unit-economics-positioning.json" in doc
    assert "stage55_u1_unit_economics_positioning.json" in doc
    assert "cac_ltv_measured_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert (
        "economics" in doc.lower()
        or "competitive" in doc.lower()
        or "positioning" in doc.lower()
        or "cac" in doc.lower()
    )

    readme = _read("ops/mvp/README.md")
    assert "Stage 55 U1" in readme
    assert "UNIT_ECONOMICS_POSITIONING_MVP.md" in readme
    assert "unit-economics-positioning.json" in readme


def test_u1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_55_PLAN.md")
    u1_line = [ln for ln in plan.splitlines() if "| **U1** |" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_unit_economics_positioning_u1.py" in plan
    assert (
        "U1 next" in plan
        or "U1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H55x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_unit_economics_positioning_u1.py" in launch
    assert "Stage 55 U1" in launch
    assert "UNIT_ECONOMICS_POSITIONING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 55 U1" in roadmap
    assert "test_unit_economics_positioning_u1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 55 U1" in pr
    assert "test_unit_economics_positioning_u1.py" in pr or "UNIT_ECONOMICS_POSITIONING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "55",
        "workstream": "U1",
        "passed": True,
        "doc": "docs/UNIT_ECONOMICS_POSITIONING_MVP.md",
        "register": "ops/mvp/unit-economics-positioning.json",
        "packaging_complete": True,
        "cac_ltv_measured_claimed": False,
        "arpu_payback_measured_claimed": False,
        "competitive_superiority_proven": False,
        "win_loss_analysis_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["cac_ltv_measured_claimed"] is False
    assert loaded["competitive_superiority_proven"] is False
    assert loaded["step_count"] >= 10
