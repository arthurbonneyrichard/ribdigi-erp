"""Stage 78 P1 — Commercial pricing honesty (not public pricing portal Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-pricing.json"
PRICING = ROOT / "ops" / "mvp" / "pricing-transparency.json"
BILLING = ROOT / "ops" / "mvp" / "commercial-billing-deferred.json"
TERMS = ROOT / "ops" / "mvp" / "commercial-terms.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage78_p1_commercial_pricing.json"

REQUIRED_IDS = {
    "cp-owner-outline", "cp-pricing-transparency", "cp-billing-commercial", "cp-billing-deferred",
    "cp-terms", "cp-adr002", "cp-plan-honesty", "cp-list-price-review", "cp-pricing-remaining", "cp-golive-remaining",
}
REQUIRED_CATEGORIES = {"pricing", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_pricing_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "78" and mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    for k in ("public_pricing_portal_claimed", "list_price_binding_claimed", "checkout_pricing_live",
              "paid_billing_claimed", "billing_complete_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_PRICING_MVP.md"
    assert "stage78_p1_commercial_pricing.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cp-pricing-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cp-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("pricing" in d.lower() or "billing" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage78_plan"], mapping["pricing_doc"], mapping["pricing"],
                mapping["billing_commercial_doc"], mapping["billing_commercial"],
                mapping["billing_deferred_doc"], mapping["billing_deferred"],
                mapping["terms_doc"], mapping["terms"], mapping["adr_002"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_pricing_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    billing = json.loads(BILLING.read_text(encoding="utf-8"))
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    assert mapping["public_pricing_portal_claimed"] is False
    for key in ("public_pricing_portal_claimed", "checkout_pricing_live", "paid_billing_claimed", "go_live_claimed"):
        if key in pricing:
            assert pricing[key] is False
    for key in ("billing_complete_claimed", "payment_provider_claimed", "go_live_claimed"):
        if key in billing:
            assert billing[key] is False
    for key in ("tos_signed_claimed", "go_live_claimed"):
        if key in terms:
            assert terms[key] is False
    plan = _read("docs/STAGE_78_PLAN.md")
    assert "Pricing" in plan and "Professional Services" in plan


def test_commercial_pricing_doc_and_readme():
    doc = _read("docs/COMMERCIAL_PRICING_MVP.md")
    assert "Stage 78 P1" in doc and "test_commercial_pricing_p1.py" in doc
    assert "commercial-pricing.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 78 P1" in readme and "COMMERCIAL_PRICING_MVP.md" in readme and "commercial-pricing.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_78_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "test_commercial_pricing_p1.py" in plan
    assert any(x in plan for x in ("P1 next", "P1 complete", "S1 next", "S1 complete", "D1 next", "D1 complete", "H78x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_pricing_p1.py" in launch and "Stage 78 P1" in launch and "COMMERCIAL_PRICING_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 78 P1" in roadmap and "test_commercial_pricing_p1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 78 P1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "78", "workstream": "P1", "passed": True, "doc": "docs/COMMERCIAL_PRICING_MVP.md",
               "register": "ops/mvp/commercial-pricing.json", "packaging_complete": True,
               "public_pricing_portal_claimed": False, "checkout_pricing_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["public_pricing_portal_claimed"] is False and loaded["step_count"] >= 10
