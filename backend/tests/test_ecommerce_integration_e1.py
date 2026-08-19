"""Stage 59 E1 — e-commerce integration honesty (not live Shopify / WooCommerce Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ecommerce-integration.json"
MARKETPLACE = ROOT / "ops" / "mvp" / "marketplace-presence.json"
API_COMM = ROOT / "ops" / "mvp" / "api-integration-commercial.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage59_e1_ecommerce_integration.json"

REQUIRED_IDS = {
    "ec-product-overview",
    "ec-marketplace",
    "ec-api-commercial",
    "ec-digital-marketing",
    "ec-partner-sales",
    "ec-roadmap-backlog",
    "ec-plan-honesty",
    "ec-shopify-remaining",
    "ec-woocommerce-remaining",
    "ec-sync-remaining",
}
REQUIRED_CATEGORIES = {"ecommerce", "channel", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ecommerce_integration_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "59"
    assert mapping["workstream"] == "E1"
    assert mapping["packaging_complete"] is True
    assert mapping["shopify_connector_live_claimed"] is False
    assert mapping["woocommerce_connector_live_claimed"] is False
    assert mapping["ecommerce_sync_program_live"] is False
    assert mapping["ecommerce_integration_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ECOMMERCE_INTEGRATION_MVP.md"
    assert "stage59_e1_ecommerce_integration.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ec-shopify-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ec-woocommerce-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "shopify" in d.lower()
        or "woocommerce" in d.lower()
        or "e-commerce" in d.lower()
        or "ecommerce" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["api_integration_commercial"],
        mapping["api_integration_commercial_doc"],
        mapping["digital_marketing"],
        mapping["digital_marketing_doc"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["direct_sales"],
        mapping["direct_sales_doc"],
        mapping["development_roadmap"],
        mapping["stage59_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_ecommerce_integration_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    api_comm = json.loads(API_COMM.read_text(encoding="utf-8"))
    assert mapping["shopify_connector_live_claimed"] is False
    assert mapping["woocommerce_connector_live_claimed"] is False
    for key in ("marketplace_listing_live", "addon_catalog_live"):
        if key in marketplace:
            assert marketplace[key] is False
    for key in (
        "api_rate_limit_upgrade_billing_live",
        "connector_fee_billing_claimed",
        "api_commercial_catalog_live",
        "integration_revenue_live",
    ):
        if key in api_comm:
            assert api_comm[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "Shopify" in po
        or "WooCommerce" in po
        or "E-commerce" in po
        or "e-commerce" in po.lower()
    )


def test_ecommerce_integration_doc_and_readme():
    doc = _read("docs/ECOMMERCE_INTEGRATION_MVP.md")
    assert "Stage 59 E1" in doc
    assert "test_ecommerce_integration_e1.py" in doc
    assert "ecommerce-integration.json" in doc
    assert "stage59_e1_ecommerce_integration.json" in doc
    assert "shopify_connector_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "shopify" in doc.lower() or "woocommerce" in doc.lower() or "e-commerce" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 59 E1" in readme
    assert "ECOMMERCE_INTEGRATION_MVP.md" in readme
    assert "ecommerce-integration.json" in readme


def test_e1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_59_PLAN.md")
    e1_line = [ln for ln in plan.splitlines() if "| **E1** |" in ln][0]
    assert "COMPLETE" in e1_line
    assert "test_ecommerce_integration_e1.py" in plan
    assert (
        "E1 next" in plan
        or "E1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H59x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ecommerce_integration_e1.py" in launch
    assert "Stage 59 E1" in launch
    assert "ECOMMERCE_INTEGRATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 59 E1" in roadmap
    assert "test_ecommerce_integration_e1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 59 E1" in pr
    assert "test_ecommerce_integration_e1.py" in pr or "ECOMMERCE_INTEGRATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "59",
        "workstream": "E1",
        "passed": True,
        "doc": "docs/ECOMMERCE_INTEGRATION_MVP.md",
        "register": "ops/mvp/ecommerce-integration.json",
        "packaging_complete": True,
        "shopify_connector_live_claimed": False,
        "woocommerce_connector_live_claimed": False,
        "ecommerce_sync_program_live": False,
        "ecommerce_integration_program_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["shopify_connector_live_claimed"] is False
    assert loaded["woocommerce_connector_live_claimed"] is False
    assert loaded["step_count"] >= 10
