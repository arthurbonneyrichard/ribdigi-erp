"""Stage 51 A1 — add-on services honesty (not live add-on catalog Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "addon-services.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
MARKETPLACE = ROOT / "ops" / "mvp" / "marketplace-presence.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage51_a1_addon_services.json"

REQUIRED_IDS = {
    "ao-product-overview",
    "ao-billing-deferred",
    "ao-marketplace-adjacency",
    "ao-pricing-adjacency",
    "ao-sow-adjacency",
    "ao-deferred-adr",
    "ao-roadmap-backlog",
    "ao-plan-honesty",
    "ao-catalog-remaining",
    "ao-billing-remaining",
}
REQUIRED_CATEGORIES = {"addon", "services", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_addon_services_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "51"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["addon_catalog_live"] is False
    assert mapping["addon_billing_claimed"] is False
    assert mapping["sms_email_credits_live"] is False
    assert mapping["premium_ai_addon_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ADDON_SERVICES_MVP.md"
    assert "stage51_a1_addon_services.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ao-catalog-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ao-billing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "add-on" in d.lower() or "addon" in d.lower() or "billing" in d.lower() or "sms" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["pricing_transparency"],
        mapping["pricing_transparency_doc"],
        mapping["professional_services_sow"],
        mapping["professional_services_sow_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage51_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_addon_services_aligns_billing_and_marketplace():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert mapping["addon_catalog_live"] is False
    assert mapping["addon_billing_claimed"] is False
    assert billing.get("billing_complete_claimed") is False
    assert billing.get("payment_provider_claimed") is False
    assert billing.get("checkout_success_claimed") is False
    assert marketplace.get("marketplace_listing_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "add-on" in po.lower() or "Add-On" in po or "SMS" in po or "storage" in po.lower()
    bd = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "billing" in bd.lower() or "ADR-002" in bd or "deferred" in bd.lower()


def test_addon_services_doc_and_readme():
    doc = _read("docs/ADDON_SERVICES_MVP.md")
    assert "Stage 51 A1" in doc
    assert "test_addon_services_a1.py" in doc
    assert "addon-services.json" in doc
    assert "stage51_a1_addon_services.json" in doc
    assert "addon_catalog_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "add-on" in doc.lower() or "addon" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 51 A1" in readme
    assert "ADDON_SERVICES_MVP.md" in readme
    assert "addon-services.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_51_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_addon_services_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H51x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_addon_services_a1.py" in launch
    assert "Stage 51 A1" in launch
    assert "ADDON_SERVICES_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 51 A1" in roadmap
    assert "test_addon_services_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 51 A1" in pr
    assert "test_addon_services_a1.py" in pr or "ADDON_SERVICES_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "51",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/ADDON_SERVICES_MVP.md",
        "register": "ops/mvp/addon-services.json",
        "packaging_complete": True,
        "addon_catalog_live": False,
        "addon_billing_claimed": False,
        "sms_email_credits_live": False,
        "premium_ai_addon_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["addon_catalog_live"] is False
    assert loaded["addon_billing_claimed"] is False
    assert loaded["step_count"] >= 10
