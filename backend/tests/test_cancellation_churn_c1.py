"""Stage 53 C1 — cancellation / refund / churn honesty (not live cancellation portal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cancellation-churn.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
RENEWAL = ROOT / "ops" / "mvp" / "subscription-renewal.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage53_c1_cancellation_churn.json"

REQUIRED_IDS = {
    "cc-product-overview",
    "cc-billing-deferred",
    "cc-renewal-adjacency",
    "cc-api-adjacency",
    "cc-trial-adjacency",
    "cc-deferred-adr",
    "cc-roadmap-backlog",
    "cc-plan-honesty",
    "cc-portal-remaining",
    "cc-refund-churn-remaining",
}
REQUIRED_CATEGORIES = {"cancellation", "churn", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cancellation_churn_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "53"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["cancellation_portal_live"] is False
    assert mapping["refund_processing_claimed"] is False
    assert mapping["churn_measurement_live"] is False
    assert mapping["cancellation_policy_enforced"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CANCELLATION_CHURN_MVP.md"
    assert "stage53_c1_cancellation_churn.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "cc-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cc-refund-churn-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "cancel" in d.lower() or "refund" in d.lower() or "churn" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["subscription_renewal"],
        mapping["subscription_renewal_doc"],
        mapping["api_integration_commercial"],
        mapping["api_integration_commercial_doc"],
        mapping["freemium_trial"],
        mapping["freemium_trial_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage53_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_cancellation_churn_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    renewal = json.loads(RENEWAL.read_text(encoding="utf-8"))
    assert mapping["cancellation_portal_live"] is False
    assert mapping["refund_processing_claimed"] is False
    for key in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed"):
        if key in billing:
            assert billing[key] is False
    if "auto_renewal_billing_live" in renewal:
        assert renewal["auto_renewal_billing_live"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Churn" in po
        or "churn" in po.lower()
        or "subscription" in po.lower()
        or "SaaS" in po
    )


def test_cancellation_churn_doc_and_readme():
    doc = _read("docs/CANCELLATION_CHURN_MVP.md")
    assert "Stage 53 C1" in doc
    assert "test_cancellation_churn_c1.py" in doc
    assert "cancellation-churn.json" in doc
    assert "stage53_c1_cancellation_churn.json" in doc
    assert "cancellation_portal_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "cancel" in doc.lower() or "churn" in doc.lower() or "refund" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 53 C1" in readme
    assert "CANCELLATION_CHURN_MVP.md" in readme
    assert "cancellation-churn.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_53_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_cancellation_churn_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H53x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_cancellation_churn_c1.py" in launch
    assert "Stage 53 C1" in launch
    assert "CANCELLATION_CHURN_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 53 C1" in roadmap
    assert "test_cancellation_churn_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 53 C1" in pr
    assert "test_cancellation_churn_c1.py" in pr or "CANCELLATION_CHURN_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "53",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/CANCELLATION_CHURN_MVP.md",
        "register": "ops/mvp/cancellation-churn.json",
        "packaging_complete": True,
        "cancellation_portal_live": False,
        "refund_processing_claimed": False,
        "churn_measurement_live": False,
        "cancellation_policy_enforced": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["cancellation_portal_live"] is False
    assert loaded["refund_processing_claimed"] is False
    assert loaded["step_count"] >= 10
