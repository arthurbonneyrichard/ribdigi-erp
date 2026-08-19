"""Stage 65 P1 — Controlled business pilot honesty (not live pilot Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "business-pilot.json"
FIRST = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
E2E = ROOT / "ops" / "mvp" / "e2e-org-bootstrap.json"
PIPE = ROOT / "ops" / "mvp" / "release-pipeline.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage65_p1_business_pilot.json"

REQUIRED_IDS = {
    "bp-owner-outline",
    "bp-first-tenant",
    "bp-implementation",
    "bp-e2e-bootstrap",
    "bp-e2e-sale",
    "bp-operator-remaining",
    "bp-customer-training",
    "bp-release-pipeline",
    "bp-plan-honesty",
    "bp-pilot-remaining",
    "bp-feedback-remaining",
}
REQUIRED_CATEGORIES = {"pilot", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_business_pilot_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "65"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["controlled_business_pilot_live_claimed"] is False
    assert mapping["real_workflow_feedback_claimed"] is False
    assert mapping["pilot_bugfix_program_live"] is False
    assert mapping["business_pilot_program_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["doc"] == "docs/BUSINESS_PILOT_MVP.md"
    assert "stage65_p1_business_pilot.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "bp-pilot-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "bp-feedback-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "pilot" in d.lower() or "feedback" in d.lower() or "bug" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage65_plan"],
        mapping["release_pipeline"],
        mapping["release_pipeline_doc"],
        mapping["first_tenant"],
        mapping["first_tenant_doc"],
        mapping["implementation_onboarding"],
        mapping["implementation_onboarding_doc"],
        mapping["e2e_org_bootstrap"],
        mapping["e2e_org_bootstrap_doc"],
        mapping["e2e_sale_payment"],
        mapping["e2e_sale_payment_doc"],
        mapping["operator_remaining"],
        mapping["operator_remaining_doc"],
        mapping["customer_training"],
        mapping["customer_training_doc"],
        mapping["development_roadmap"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_business_pilot_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    e2e = json.loads(E2E.read_text(encoding="utf-8"))
    pipe = json.loads(PIPE.read_text(encoding="utf-8"))
    assert mapping["controlled_business_pilot_live_claimed"] is False
    assert mapping["real_workflow_feedback_claimed"] is False
    for key in (
        "first_tenant_onboarded_claimed",
        "live_onboarding_success_claimed",
        "demo_tenant_claimed",
    ):
        if key in first:
            assert first[key] is False
    for key in ("e2e_smoke_executed_claimed", "live_bootstrap_claimed", "demo_tenant_claimed"):
        if key in e2e:
            assert e2e[key] is False
    for key in ("mvp_release_candidate_signed", "release_pipeline_live_claimed"):
        if key in pipe:
            assert pipe[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_65_PLAN.md")
    assert "Controlled Business Pilot" in plan or "pilot" in plan.lower()
    assert "Real Workflow Feedback" in plan or "feedback" in plan.lower()


def test_business_pilot_doc_and_readme():
    doc = _read("docs/BUSINESS_PILOT_MVP.md")
    assert "Stage 65 P1" in doc
    assert "test_business_pilot_p1.py" in doc
    assert "business-pilot.json" in doc
    assert "stage65_p1_business_pilot.json" in doc
    assert "controlled_business_pilot_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "pilot" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 65 P1" in readme
    assert "BUSINESS_PILOT_MVP.md" in readme
    assert "business-pilot.json" in readme


def test_p1_plan_launch_roadmap():
    plan = _read("docs/STAGE_65_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_business_pilot_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H65x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_business_pilot_p1.py" in launch
    assert "Stage 65 P1" in launch
    assert "BUSINESS_PILOT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 65 P1" in roadmap
    assert "test_business_pilot_p1.py" in roadmap

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "65",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/BUSINESS_PILOT_MVP.md",
        "register": "ops/mvp/business-pilot.json",
        "packaging_complete": True,
        "controlled_business_pilot_live_claimed": False,
        "real_workflow_feedback_claimed": False,
        "pilot_bugfix_program_live": False,
        "business_pilot_program_live": False,
        "demo_tenant_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["controlled_business_pilot_live_claimed"] is False
    assert loaded["real_workflow_feedback_claimed"] is False
    assert loaded["step_count"] >= 10
