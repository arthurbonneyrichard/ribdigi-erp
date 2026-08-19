"""Stage 58 B1 — business metrics honesty (not measured MRR / paying customers / NRR Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "business-metrics.json"
SUCCESS = ROOT / "ops" / "mvp" / "success-metrics.json"
ECONOMICS = ROOT / "ops" / "mvp" / "unit-economics-positioning.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage58_b1_business_metrics.json"

REQUIRED_IDS = {
    "bm-product-overview",
    "bm-success-metrics",
    "bm-unit-economics",
    "bm-freemium-trial",
    "bm-subscription-renewal",
    "bm-cancellation-churn",
    "bm-billing-deferred",
    "bm-plan-honesty",
    "bm-mrr-remaining",
    "bm-nrr-remaining",
}
REQUIRED_CATEGORIES = {"business", "metrics", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_business_metrics_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "58"
    assert mapping["workstream"] == "B1"
    assert mapping["packaging_complete"] is True
    assert mapping["mrr_measured_claimed"] is False
    assert mapping["paying_customers_measured_claimed"] is False
    assert mapping["nrr_grr_measured_claimed"] is False
    assert mapping["business_metrics_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/BUSINESS_METRICS_MVP.md"
    assert "stage58_b1_business_metrics.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "bm-mrr-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "bm-nrr-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "mrr" in d.lower()
        or "paying" in d.lower()
        or "nrr" in d.lower()
        or "grr" in d.lower()
        or "trial" in d.lower()
        or "business" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["success_metrics"],
        mapping["success_metrics_doc"],
        mapping["unit_economics_positioning"],
        mapping["unit_economics_positioning_doc"],
        mapping["freemium_trial"],
        mapping["freemium_trial_doc"],
        mapping["subscription_renewal"],
        mapping["subscription_renewal_doc"],
        mapping["cancellation_churn"],
        mapping["cancellation_churn_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["development_roadmap"],
        mapping["stage58_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_business_metrics_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    success = json.loads(SUCCESS.read_text(encoding="utf-8"))
    economics = json.loads(ECONOMICS.read_text(encoding="utf-8"))
    assert mapping["mrr_measured_claimed"] is False
    assert mapping["paying_customers_measured_claimed"] is False
    for key in ("mau_measured_claimed", "nps_measured_claimed", "uptime_sla_measured_claimed"):
        if key in success:
            assert success[key] is False
    for key in ("cac_ltv_measured_claimed", "arpu_payback_measured_claimed"):
        if key in economics:
            assert economics[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "MRR" in po
        or "Paying Customers" in po
        or "Net Revenue Retention" in po
        or "Trial-to-Paid" in po
    )


def test_business_metrics_doc_and_readme():
    doc = _read("docs/BUSINESS_METRICS_MVP.md")
    assert "Stage 58 B1" in doc
    assert "test_business_metrics_b1.py" in doc
    assert "business-metrics.json" in doc
    assert "stage58_b1_business_metrics.json" in doc
    assert "mrr_measured_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "business" in doc.lower() or "mrr" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 58 B1" in readme
    assert "BUSINESS_METRICS_MVP.md" in readme
    assert "business-metrics.json" in readme


def test_b1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_58_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_business_metrics_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "I1 next" in plan
        or "I1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H58x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_business_metrics_b1.py" in launch
    assert "Stage 58 B1" in launch
    assert "BUSINESS_METRICS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 58 B1" in roadmap
    assert "test_business_metrics_b1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 58 B1" in pr
    assert "test_business_metrics_b1.py" in pr or "BUSINESS_METRICS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "58",
        "workstream": "B1",
        "passed": True,
        "doc": "docs/BUSINESS_METRICS_MVP.md",
        "register": "ops/mvp/business-metrics.json",
        "packaging_complete": True,
        "mrr_measured_claimed": False,
        "paying_customers_measured_claimed": False,
        "nrr_grr_measured_claimed": False,
        "business_metrics_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["mrr_measured_claimed"] is False
    assert loaded["paying_customers_measured_claimed"] is False
    assert loaded["step_count"] >= 10
