"""Stage 52 R1 — subscription renewal honesty (not live annual-discount / auto-renewal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "subscription-renewal.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
INDUSTRY = ROOT / "ops" / "mvp" / "industry-partnerships.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage52_r1_subscription_renewal.json"

REQUIRED_IDS = {
    "sr-product-overview",
    "sr-billing-deferred",
    "sr-pricing-adjacency",
    "sr-industry-adjacency",
    "sr-trial-adjacency",
    "sr-deferred-adr",
    "sr-roadmap-backlog",
    "sr-plan-honesty",
    "sr-discount-remaining",
    "sr-renewal-remaining",
}
REQUIRED_CATEGORIES = {"renewal", "discount", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_subscription_renewal_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "52"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["annual_discount_enforcement_claimed"] is False
    assert mapping["auto_renewal_billing_live"] is False
    assert mapping["upgrade_downgrade_live"] is False
    assert mapping["renewal_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SUBSCRIPTION_RENEWAL_MVP.md"
    assert "stage52_r1_subscription_renewal.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sr-discount-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sr-renewal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "discount" in d.lower() or "renewal" in d.lower() or "billing" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["freemium_trial"],
        mapping["freemium_trial_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage52_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_subscription_renewal_aligns_billing_and_industry():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    industry = json.loads(INDUSTRY.read_text(encoding="utf-8"))
    assert mapping["annual_discount_enforcement_claimed"] is False
    assert mapping["auto_renewal_billing_live"] is False
    assert billing.get("billing_complete_claimed") is False
    assert billing.get("payment_provider_claimed") is False
    assert billing.get("checkout_success_claimed") is False
    assert industry.get("industry_partnership_program_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "Annual billing" in po or "auto-renewal" in po.lower() or "20%" in po or "discount" in po.lower()
    bd = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "billing" in bd.lower() or "ADR-002" in bd or "deferred" in bd.lower()


def test_subscription_renewal_doc_and_readme():
    doc = _read("docs/SUBSCRIPTION_RENEWAL_MVP.md")
    assert "Stage 52 R1" in doc
    assert "test_subscription_renewal_r1.py" in doc
    assert "subscription-renewal.json" in doc
    assert "stage52_r1_subscription_renewal.json" in doc
    assert "annual_discount_enforcement_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "renewal" in doc.lower() or "discount" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 52 R1" in readme
    assert "SUBSCRIPTION_RENEWAL_MVP.md" in readme
    assert "subscription-renewal.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_52_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_subscription_renewal_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H52x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_subscription_renewal_r1.py" in launch
    assert "Stage 52 R1" in launch
    assert "SUBSCRIPTION_RENEWAL_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 52 R1" in roadmap
    assert "test_subscription_renewal_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 52 R1" in pr
    assert "test_subscription_renewal_r1.py" in pr or "SUBSCRIPTION_RENEWAL_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "52",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/SUBSCRIPTION_RENEWAL_MVP.md",
        "register": "ops/mvp/subscription-renewal.json",
        "packaging_complete": True,
        "annual_discount_enforcement_claimed": False,
        "auto_renewal_billing_live": False,
        "upgrade_downgrade_live": False,
        "renewal_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["annual_discount_enforcement_claimed"] is False
    assert loaded["auto_renewal_billing_live"] is False
    assert loaded["step_count"] >= 10
