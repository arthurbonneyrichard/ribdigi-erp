"""Stage 49 L1 — pricing transparency honesty (not public pricing portal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "pricing-transparency.json"
BILLING = ROOT / "ops" / "mvp" / "billing-deferred-honesty.json"
PARTNER = ROOT / "ops" / "mvp" / "partner-reseller.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage49_l1_pricing_transparency.json"

REQUIRED_IDS = {
    "pt-product-overview",
    "pt-billing-deferred",
    "pt-adr-002",
    "pt-partner-adjacency",
    "pt-deferred-adr",
    "pt-tos-adjacency",
    "pt-roadmap-backlog",
    "pt-plan-honesty",
    "pt-portal-remaining",
    "pt-checkout-remaining",
}
REQUIRED_CATEGORIES = {"pricing", "transparency", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pricing_transparency_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "49"
    assert mapping["workstream"] == "L1"
    assert mapping["packaging_complete"] is True
    assert mapping["public_pricing_portal_claimed"] is False
    assert mapping["list_price_binding_claimed"] is False
    assert mapping["checkout_pricing_live"] is False
    assert mapping["paid_billing_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/PRICING_TRANSPARENCY_MVP.md"
    assert "stage49_l1_pricing_transparency.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "pt-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pt-checkout-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "pricing" in d.lower() or "checkout" in d.lower() or "billing" in d.lower() or "list" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["product_overview"],
        mapping["billing_deferred"],
        mapping["billing_deferred_doc"],
        mapping["adr_002"],
        mapping["partner_reseller"],
        mapping["partner_reseller_doc"],
        mapping["deferred_adr_register"],
        mapping["deferred_adr_register_doc"],
        mapping["tos_aup"],
        mapping["tos_aup_doc"],
        mapping["development_roadmap"],
        mapping["stage49_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_pricing_transparency_aligns_billing_deferred():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    partner = json.loads(PARTNER.read_text(encoding="utf-8"))
    assert mapping["public_pricing_portal_claimed"] is False
    assert mapping["checkout_pricing_live"] is False
    assert billing.get("billing_complete_claimed") is False
    assert billing.get("payment_provider_claimed") is False
    assert billing.get("checkout_success_claimed") is False
    assert partner.get("partner_program_live") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "pricing" in po.lower() or "$29" in po or "Edition" in po
    bd = _read("docs/BILLING_DEFERRED_HONESTY_MVP.md")
    assert "billing" in bd.lower() or "ADR-002" in bd or "deferred" in bd.lower()


def test_pricing_transparency_doc_and_readme():
    doc = _read("docs/PRICING_TRANSPARENCY_MVP.md")
    assert "Stage 49 L1" in doc
    assert "test_pricing_transparency_l1.py" in doc
    assert "pricing-transparency.json" in doc
    assert "stage49_l1_pricing_transparency.json" in doc
    assert "public_pricing_portal_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "pricing" in doc.lower() or "price" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 49 L1" in readme
    assert "PRICING_TRANSPARENCY_MVP.md" in readme
    assert "pricing-transparency.json" in readme


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_49_PLAN.md")
    l1_line = [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_pricing_transparency_l1.py" in plan
    assert (
        "L1 next" in plan
        or "L1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H49x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pricing_transparency_l1.py" in launch
    assert "Stage 49 L1" in launch
    assert "PRICING_TRANSPARENCY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 49 L1" in roadmap
    assert "test_pricing_transparency_l1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 49 L1" in pr
    assert "test_pricing_transparency_l1.py" in pr or "PRICING_TRANSPARENCY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "49",
        "workstream": "L1",
        "passed": True,
        "doc": "docs/PRICING_TRANSPARENCY_MVP.md",
        "register": "ops/mvp/pricing-transparency.json",
        "packaging_complete": True,
        "public_pricing_portal_claimed": False,
        "list_price_binding_claimed": False,
        "checkout_pricing_live": False,
        "paid_billing_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["public_pricing_portal_claimed"] is False
    assert loaded["checkout_pricing_live"] is False
    assert loaded["step_count"] >= 10
