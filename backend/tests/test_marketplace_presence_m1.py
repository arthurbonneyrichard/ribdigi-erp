"""Stage 51 M1 — marketplace presence honesty (not live marketplace listing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "marketplace-presence.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage51_m1_marketplace_presence.json"

REQUIRED_IDS = {
    "mp-product-overview",
    "mp-partner-adjacency",
    "mp-referral-adjacency",
    "mp-pricing-adjacency",
    "mp-billing-deferred",
    "mp-deferred-adr",
    "mp-roadmap-backlog",
    "mp-plan-honesty",
    "mp-listing-remaining",
    "mp-appstore-remaining",
}
REQUIRED_CATEGORIES = {"marketplace", "presence", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_marketplace_presence_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "51"
    assert mapping["workstream"] == "M1"
    assert mapping["packaging_complete"] is True
    assert mapping["marketplace_listing_live"] is False
    assert mapping["app_store_presence_claimed"] is False
    assert mapping["plugin_marketplace_live"] is False
    assert mapping["marketplace_revenue_share_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/MARKETPLACE_PRESENCE_MVP.md"
    assert "stage51_m1_marketplace_presence.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "mp-listing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "mp-appstore-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "marketplace" in d.lower() or "app-store" in d.lower() or "plugin" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["referral_program"],
        mapping["referral_program_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage51_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_marketplace_presence_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    assert mapping["marketplace_listing_live"] is False
    assert mapping["app_store_presence_claimed"] is False
    assert billing.get("billing_complete_claimed") is False
    assert partner.get("partner_program_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "marketplace" in po.lower() or "Marketplace" in po
    assert "app store" in po.lower() or "app stores" in po.lower() or "Marketplace" in po


def test_marketplace_presence_doc_and_readme():
    doc = _read("docs/MARKETPLACE_PRESENCE_MVP.md")
    assert "Stage 51 M1" in doc
    assert "test_marketplace_presence_m1.py" in doc
    assert "marketplace-presence.json" in doc
    assert "stage51_m1_marketplace_presence.json" in doc
    assert "marketplace_listing_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "marketplace" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 51 M1" in readme
    assert "MARKETPLACE_PRESENCE_MVP.md" in readme
    assert "marketplace-presence.json" in readme


def test_m1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_51_PLAN.md")
    m1_line = [ln for ln in plan.splitlines() if "| **M1** |" in ln][0]
    assert "COMPLETE" in m1_line
    assert "test_marketplace_presence_m1.py" in plan
    assert (
        "M1 next" in plan
        or "M1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H51x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_marketplace_presence_m1.py" in launch
    assert "Stage 51 M1" in launch
    assert "MARKETPLACE_PRESENCE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 51 M1" in roadmap
    assert "test_marketplace_presence_m1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 51 M1" in pr
    assert "test_marketplace_presence_m1.py" in pr or "MARKETPLACE_PRESENCE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "51",
        "workstream": "M1",
        "passed": True,
        "doc": "docs/MARKETPLACE_PRESENCE_MVP.md",
        "register": "ops/mvp/marketplace-presence.json",
        "packaging_complete": True,
        "marketplace_listing_live": False,
        "app_store_presence_claimed": False,
        "plugin_marketplace_live": False,
        "marketplace_revenue_share_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["marketplace_listing_live"] is False
    assert loaded["app_store_presence_claimed"] is False
    assert loaded["step_count"] >= 10
