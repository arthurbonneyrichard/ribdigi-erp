"""Stage 66 T1 — First tenant go-live honesty (not first paying tenant Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-golive.json"
FIRST = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
PILOT = ROOT / "ops" / "mvp" / "business-pilot.json"
LAUNCH = ROOT / "ops" / "mvp" / "production-launch.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage66_t1_first_tenant_golive.json"

REQUIRED_IDS = {
    "ftg-owner-outline",
    "ftg-first-tenant",
    "ftg-business-pilot",
    "ftg-implementation",
    "ftg-operator-handoff",
    "ftg-production-launch",
    "ftg-mvp-declaration",
    "ftg-no-demo",
    "ftg-plan-honesty",
    "ftg-paying-remaining",
    "ftg-onboarding-remaining",
}
REQUIRED_CATEGORIES = {"onboarding", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_first_tenant_golive_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "66"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["first_paying_tenant_claimed"] is False
    assert mapping["first_tenant_onboarded_claimed"] is False
    assert mapping["live_onboarding_success_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["first_tenant_golive_program_live"] is False
    assert mapping["doc"] == "docs/FIRST_TENANT_GOLIVE_MVP.md"
    assert "stage66_t1_first_tenant_golive.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ftg-paying-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ftg-onboarding-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "paying" in d.lower() or "onboarding" in d.lower() or "tenant" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage66_plan"],
        mapping["first_tenant_doc"],
        mapping["first_tenant"],
        mapping["business_pilot_doc"],
        mapping["business_pilot"],
        mapping["implementation_onboarding_doc"],
        mapping["implementation_onboarding"],
        mapping["operator_handoff_doc"],
        mapping["operator_handoff"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["attestation_doc"],
        mapping["attestation_matrix"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_golive_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    launch = json.loads(LAUNCH.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    assert mapping["first_paying_tenant_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    for key in ("first_tenant_onboarded_claimed", "live_onboarding_success_claimed", "demo_tenant_claimed"):
        if key in first:
            assert first[key] is False
    for key in ("controlled_business_pilot_live_claimed", "demo_tenant_claimed", "go_live_claimed"):
        if key in pilot:
            assert pilot[key] is False
    for key in ("go_live_claimed", "section_7_signed", "production_cutover_claimed"):
        if key in launch:
            assert launch[key] is False
    for key in ("go_live_claimed", "section_7_signed"):
        if key in mvp:
            assert mvp[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_66_PLAN.md")
    assert "First Paying Tenant" in plan or "first paying tenant" in plan.lower()
    assert "First Tenant Go-Live" in plan or "first tenant go-live" in plan.lower() or "T1" in plan


def test_first_tenant_golive_doc_and_readme():
    doc = _read("docs/FIRST_TENANT_GOLIVE_MVP.md")
    assert "Stage 66 T1" in doc
    assert "test_first_tenant_golive_t1.py" in doc
    assert "first-tenant-golive.json" in doc
    assert "stage66_t1_first_tenant_golive.json" in doc
    assert "first_paying_tenant_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "tenant" in doc.lower() or "onboarding" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 66 T1" in readme
    assert "FIRST_TENANT_GOLIVE_MVP.md" in readme
    assert "first-tenant-golive.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_66_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_first_tenant_golive_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H66x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_first_tenant_golive_t1.py" in launch
    assert "Stage 66 T1" in launch
    assert "FIRST_TENANT_GOLIVE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 66 T1" in roadmap
    assert "test_first_tenant_golive_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 66 T1" in pr
    assert "test_first_tenant_golive_t1.py" in pr or "FIRST_TENANT_GOLIVE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "66",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/FIRST_TENANT_GOLIVE_MVP.md",
        "register": "ops/mvp/first-tenant-golive.json",
        "packaging_complete": True,
        "first_paying_tenant_claimed": False,
        "first_tenant_onboarded_claimed": False,
        "live_onboarding_success_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "demo_tenant_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["first_paying_tenant_claimed"] is False
    assert loaded["live_onboarding_success_claimed"] is False
    assert loaded["demo_tenant_claimed"] is False
    assert loaded["step_count"] >= 10
