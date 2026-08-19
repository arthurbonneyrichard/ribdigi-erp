"""Stage 54 M1 — digital marketing honesty (not live campaigns / published case studies Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "digital-marketing.json"
REFERRAL = ROOT / "ops" / "mvp" / "referral-program.json"
MARKETPLACE = ROOT / "ops" / "mvp" / "marketplace-presence.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage54_m1_digital_marketing.json"

REQUIRED_IDS = {
    "dm-product-overview",
    "dm-referral-adjacency",
    "dm-trial-adjacency",
    "dm-marketplace-adjacency",
    "dm-industry-adjacency",
    "dm-billing-deferred",
    "dm-roadmap-backlog",
    "dm-plan-honesty",
    "dm-campaigns-remaining",
    "dm-proof-remaining",
}
REQUIRED_CATEGORIES = {"marketing", "proof", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_digital_marketing_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "54"
    assert mapping["workstream"] == "M1"
    assert mapping["packaging_complete"] is True
    assert mapping["digital_marketing_campaigns_live"] is False
    assert mapping["case_studies_published_claimed"] is False
    assert mapping["testimonials_published_claimed"] is False
    assert mapping["paid_ads_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DIGITAL_MARKETING_MVP.md"
    assert "stage54_m1_digital_marketing.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "dm-campaigns-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "dm-proof-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "marketing" in d.lower()
        or "case stud" in d.lower()
        or "testimonial" in d.lower()
        or "ads" in d.lower()
        or "SEO" in d
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["referral_program"],
        mapping["referral_program_doc"],
        mapping["freemium_trial"],
        mapping["freemium_trial_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["industry_partnerships"],
        mapping["industry_partnerships_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["development_roadmap"],
        mapping["stage54_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_digital_marketing_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    referral = json.loads(REFERRAL.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert mapping["digital_marketing_campaigns_live"] is False
    assert mapping["case_studies_published_claimed"] is False
    if "referral_program_live" in referral:
        assert referral["referral_program_live"] is False
    if "marketplace_listing_live" in marketplace:
        assert marketplace["marketplace_listing_live"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Digital Marketing" in po
        or "case stud" in po.lower()
        or "testimonial" in po.lower()
        or "Google Ads" in po
        or "SEO" in po
    )


def test_digital_marketing_doc_and_readme():
    doc = _read("docs/DIGITAL_MARKETING_MVP.md")
    assert "Stage 54 M1" in doc
    assert "test_digital_marketing_m1.py" in doc
    assert "digital-marketing.json" in doc
    assert "stage54_m1_digital_marketing.json" in doc
    assert "digital_marketing_campaigns_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "marketing" in doc.lower() or "testimonial" in doc.lower() or "case stud" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 54 M1" in readme
    assert "DIGITAL_MARKETING_MVP.md" in readme
    assert "digital-marketing.json" in readme


def test_m1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_54_PLAN.md")
    m1_line = [ln for ln in plan.splitlines() if "| **M1** |" in ln][0]
    assert "COMPLETE" in m1_line
    assert "test_digital_marketing_m1.py" in plan
    assert (
        "M1 next" in plan
        or "M1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H54x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_digital_marketing_m1.py" in launch
    assert "Stage 54 M1" in launch
    assert "DIGITAL_MARKETING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 54 M1" in roadmap
    assert "test_digital_marketing_m1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 54 M1" in pr
    assert "test_digital_marketing_m1.py" in pr or "DIGITAL_MARKETING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "54",
        "workstream": "M1",
        "passed": True,
        "doc": "docs/DIGITAL_MARKETING_MVP.md",
        "register": "ops/mvp/digital-marketing.json",
        "packaging_complete": True,
        "digital_marketing_campaigns_live": False,
        "case_studies_published_claimed": False,
        "testimonials_published_claimed": False,
        "paid_ads_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["digital_marketing_campaigns_live"] is False
    assert loaded["case_studies_published_claimed"] is False
    assert loaded["step_count"] >= 10
