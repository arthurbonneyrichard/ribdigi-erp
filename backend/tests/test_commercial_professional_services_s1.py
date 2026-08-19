"""Stage 78 S1 — Commercial professional services honesty (not signed SOW Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-professional-services.json"
SOW = ROOT / "ops" / "mvp" / "professional-services-sow.json"
PRICING = ROOT / "ops" / "mvp" / "commercial-pricing.json"
ONBOARDING = ROOT / "ops" / "mvp" / "implementation-onboarding.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage78_s1_commercial_professional_services.json"

REQUIRED_IDS = {
    "cps-owner-outline", "cps-sow", "cps-pricing", "cps-onboarding", "cps-terms",
    "cps-billing", "cps-plan-honesty", "cps-delivery-ownership", "cps-sow-remaining", "cps-golive-remaining",
}
REQUIRED_CATEGORIES = {"services", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_professional_services_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "78" and mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    for k in ("signed_sow_claimed", "professional_services_live", "implementation_delivery_claimed",
              "public_pricing_portal_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md"
    assert "stage78_s1_commercial_professional_services.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cps-sow-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cps-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("sow" in d.lower() or "services" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage78_plan"], mapping["sow_doc"], mapping["sow"],
                mapping["pricing_commercial_doc"], mapping["pricing_commercial"],
                mapping["onboarding_doc"], mapping["onboarding"], mapping["terms_doc"], mapping["terms"],
                mapping["billing_commercial_doc"], mapping["billing_commercial"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_professional_services_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    sow = json.loads(SOW.read_text(encoding="utf-8"))
    pricing = json.loads(PRICING.read_text(encoding="utf-8"))
    onboarding = json.loads(ONBOARDING.read_text(encoding="utf-8"))
    assert mapping["signed_sow_claimed"] is False
    for key in ("signed_sow_claimed", "professional_services_live", "go_live_claimed"):
        if key in sow:
            assert sow[key] is False
    for key in ("public_pricing_portal_claimed", "go_live_claimed"):
        if key in pricing:
            assert pricing[key] is False
    for key in ("go_live_claimed",):
        if key in onboarding:
            assert onboarding[key] is False
    plan = _read("docs/STAGE_78_PLAN.md")
    assert "Professional Services" in plan and "Pricing" in plan


def test_commercial_professional_services_doc_and_readme():
    doc = _read("docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md")
    assert "Stage 78 S1" in doc and "test_commercial_professional_services_s1.py" in doc
    assert "commercial-professional-services.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 78 S1" in readme and "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in readme and "commercial-professional-services.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_78_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "test_commercial_professional_services_s1.py" in plan
    assert any(x in plan for x in ("S1 next", "S1 complete", "D1 next", "D1 complete", "H78x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_professional_services_s1.py" in launch and "Stage 78 S1" in launch and "COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 78 S1" in roadmap and "test_commercial_professional_services_s1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 78 S1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "78", "workstream": "S1", "passed": True, "doc": "docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md",
               "register": "ops/mvp/commercial-professional-services.json", "packaging_complete": True,
               "signed_sow_claimed": False, "professional_services_live": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["signed_sow_claimed"] is False and loaded["step_count"] >= 10
