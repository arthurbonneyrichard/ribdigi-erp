"""Stage 63 P1 — IPO readiness honesty (not live IPO / Series B–C funding Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ipo-readiness.json"
COMPLIANCE = ROOT / "ops" / "mvp" / "compliance-readiness-register.json"
METRICS = ROOT / "ops" / "mvp" / "business-metrics.json"
UNIT = ROOT / "ops" / "mvp" / "unit-economics-positioning.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage63_p1_ipo_readiness.json"

REQUIRED_IDS = {
    "ipo-product-overview",
    "ipo-compliance",
    "ipo-residual-risk",
    "ipo-business-metrics",
    "ipo-unit-economics",
    "ipo-assurance",
    "ipo-cyber-insurance",
    "ipo-plan-honesty",
    "ipo-readiness-remaining",
    "ipo-funding-remaining",
}
REQUIRED_CATEGORIES = {"capital", "compliance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ipo_readiness_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "63"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["ipo_readiness_live_claimed"] is False
    assert mapping["series_b_c_funding_claimed"] is False
    assert mapping["capital_raise_program_live"] is False
    assert mapping["ipo_filing_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/IPO_READINESS_MVP.md"
    assert "stage63_p1_ipo_readiness.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ipo-readiness-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ipo-funding-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "ipo" in d.lower()
        or "series" in d.lower()
        or "fund" in d.lower()
        or "capital" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["compliance_readiness"],
        mapping["compliance_readiness_doc"],
        mapping["residual_risk"],
        mapping["residual_risk_doc"],
        mapping["business_metrics"],
        mapping["business_metrics_doc"],
        mapping["unit_economics_positioning"],
        mapping["unit_economics_positioning_doc"],
        mapping["assurance_evidence"],
        mapping["assurance_evidence_doc"],
        mapping["cyber_insurance"],
        mapping["cyber_insurance_doc"],
        mapping["development_roadmap"],
        mapping["stage63_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ipo_readiness_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    compliance = json.loads(COMPLIANCE.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    unit = json.loads(UNIT.read_text(encoding="utf-8"))
    assert mapping["ipo_readiness_live_claimed"] is False
    assert mapping["series_b_c_funding_claimed"] is False
    for key in (
        "soc2_complete_claimed",
        "iso27001_complete_claimed",
        "certification_complete_claimed",
    ):
        if key in compliance:
            assert compliance[key] is False
    for key in (
        "mrr_measured_claimed",
        "paying_customers_measured_claimed",
        "business_metrics_program_live",
    ):
        if key in metrics:
            assert metrics[key] is False
    for key in (
        "cac_ltv_measured_claimed",
        "competitive_superiority_proven",
    ):
        if key in unit:
            assert unit[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "IPO" in po
        or "Series B" in po
        or "funding" in po.lower()
    )


def test_ipo_readiness_doc_and_readme():
    doc = _read("docs/IPO_READINESS_MVP.md")
    assert "Stage 63 P1" in doc
    assert "test_ipo_readiness_p1.py" in doc
    assert "ipo-readiness.json" in doc
    assert "stage63_p1_ipo_readiness.json" in doc
    assert "ipo_readiness_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "ipo" in doc.lower() or "funding" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 63 P1" in readme
    assert "IPO_READINESS_MVP.md" in readme
    assert "ipo-readiness.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_63_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_ipo_readiness_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H63x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ipo_readiness_p1.py" in launch
    assert "Stage 63 P1" in launch
    assert "IPO_READINESS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 63 P1" in roadmap
    assert "test_ipo_readiness_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 63 P1" in pr
    assert "test_ipo_readiness_p1.py" in pr or "IPO_READINESS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "63",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/IPO_READINESS_MVP.md",
        "register": "ops/mvp/ipo-readiness.json",
        "packaging_complete": True,
        "ipo_readiness_live_claimed": False,
        "series_b_c_funding_claimed": False,
        "capital_raise_program_live": False,
        "ipo_filing_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["ipo_readiness_live_claimed"] is False
    assert loaded["series_b_c_funding_claimed"] is False
    assert loaded["step_count"] >= 10
