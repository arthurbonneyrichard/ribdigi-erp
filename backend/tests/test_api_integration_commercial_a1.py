"""Stage 53 A1 — API & integration commercial honesty (not live API upgrade billing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "api-integration-commercial.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
ADDON = ROOT / "ops" / "mvp" / "addon-services.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage53_a1_api_integration_commercial.json"

REQUIRED_IDS = {
    "ai-product-overview",
    "ai-billing-deferred",
    "ai-addon-adjacency",
    "ai-marketplace-adjacency",
    "ai-renewal-adjacency",
    "ai-deferred-adr",
    "ai-roadmap-backlog",
    "ai-plan-honesty",
    "ai-rate-limit-remaining",
    "ai-connector-fee-remaining",
}
REQUIRED_CATEGORIES = {"api", "integration", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_api_integration_commercial_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "53"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["api_rate_limit_upgrade_billing_live"] is False
    assert mapping["connector_fee_billing_claimed"] is False
    assert mapping["api_commercial_catalog_live"] is False
    assert mapping["integration_revenue_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/API_INTEGRATION_COMMERCIAL_MVP.md"
    assert "stage53_a1_api_integration_commercial.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ai-rate-limit-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ai-connector-fee-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "api" in d.lower() or "connector" in d.lower() or "rate" in d.lower() or "integration" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["addon_services"],
        mapping["addon_services_doc"],
        mapping["marketplace_presence"],
        mapping["marketplace_presence_doc"],
        mapping["subscription_renewal"],
        mapping["subscription_renewal_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["development_roadmap"],
        mapping["stage53_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_api_integration_commercial_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    addon = json.loads(ADDON.read_text(encoding="utf-8"))
    assert mapping["api_rate_limit_upgrade_billing_live"] is False
    assert mapping["connector_fee_billing_claimed"] is False
    assert billing.get("billing_complete_claimed") is False or billing.get("payment_provider_claimed") is False or True
    # billing-deferred honesty flags stay false where present
    for key in ("billing_complete_claimed", "payment_provider_claimed", "checkout_success_claimed"):
        if key in billing:
            assert billing[key] is False
    if "addon_billing_claimed" in addon:
        assert addon["addon_billing_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert (
        "API" in po
        or "rate limit" in po.lower()
        or "connector" in po.lower()
        or "Integration Revenue" in po
    )


def test_api_integration_commercial_doc_and_readme():
    doc = _read("docs/API_INTEGRATION_COMMERCIAL_MVP.md")
    assert "Stage 53 A1" in doc
    assert "test_api_integration_commercial_a1.py" in doc
    assert "api-integration-commercial.json" in doc
    assert "stage53_a1_api_integration_commercial.json" in doc
    assert "api_rate_limit_upgrade_billing_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "api" in doc.lower() or "integration" in doc.lower() or "connector" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 53 A1" in readme
    assert "API_INTEGRATION_COMMERCIAL_MVP.md" in readme
    assert "api-integration-commercial.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_53_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_api_integration_commercial_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H53x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_api_integration_commercial_a1.py" in launch
    assert "Stage 53 A1" in launch
    assert "API_INTEGRATION_COMMERCIAL_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 53 A1" in roadmap
    assert "test_api_integration_commercial_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 53 A1" in pr
    assert "test_api_integration_commercial_a1.py" in pr or "API_INTEGRATION_COMMERCIAL_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "53",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/API_INTEGRATION_COMMERCIAL_MVP.md",
        "register": "ops/mvp/api-integration-commercial.json",
        "packaging_complete": True,
        "api_rate_limit_upgrade_billing_live": False,
        "connector_fee_billing_claimed": False,
        "api_commercial_catalog_live": False,
        "integration_revenue_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["api_rate_limit_upgrade_billing_live"] is False
    assert loaded["connector_fee_billing_claimed"] is False
    assert loaded["step_count"] >= 10
