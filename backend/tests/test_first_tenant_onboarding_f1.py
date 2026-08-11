"""Stage 33 F1 — first-tenant onboarding (not live onboarding success Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
HANDOFF = ROOT / "ops" / "mvp" / "operator-handoff.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
DECLARATION = ROOT / "ops" / "mvp" / "mvp-declaration.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage33_f1_first_tenant_onboarding.json"

REQUIRED_IDS = {
    "ft-env-ready",
    "ft-no-demo",
    "ft-register-admin",
    "ft-rbac-smoke",
    "ft-api-key",
    "ft-onboarding-checklist",
    "ft-core-erp-smoke",
    "ft-launch-sections",
    "ft-ops-takeover",
    "ft-section-7",
}
REQUIRED_CATEGORIES = {
    "environment",
    "honesty",
    "tenant_lifecycle",
    "security",
    "product_onboarding",
    "erp_smoke",
    "launch",
    "operations",
    "go_live",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_first_tenant_onboarding_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "33"
    assert mapping["workstream"] == "F1"
    assert mapping["packaging_complete"] is True
    assert mapping["first_tenant_onboarded_claimed"] is False
    assert mapping["live_onboarding_success_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["doc"] == "docs/FIRST_TENANT_ONBOARDING_MVP.md"
    assert "stage33_f1_first_tenant_onboarding.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ft-section-7" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ft-no-demo" for s in steps)
    assert any("onboard" in d.lower() or "demo" in d.lower() or "§7" in d for d in mapping["deferred"])
    for rel in (
        mapping["operator_handoff"],
        mapping["mvp_declaration"],
        mapping["operator_remaining_register"],
        mapping["launch_checklist"],
        mapping["cutover_checklist"],
        mapping["attestation_matrix"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_onboarding_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))

    assert handoff["handoff_complete_claimed"] is False
    assert handoff["go_live_claimed"] is False
    assert handoff["section_7_signed"] is False
    assert remaining["attestation_claimed"] is False
    assert remaining["live_runs_certified"] is False
    assert declaration["go_live_claimed"] is False
    assert declaration["packaging_complete"] is True
    assert mapping["first_tenant_onboarded_claimed"] is False
    assert mapping["live_onboarding_success_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False


def test_first_tenant_onboarding_doc_and_readme():
    doc = _read("docs/FIRST_TENANT_ONBOARDING_MVP.md")
    assert "Stage 33 F1" in doc
    assert "test_first_tenant_onboarding_f1.py" in doc
    assert "first-tenant-onboarding.json" in doc
    assert "stage33_f1_first_tenant_onboarding.json" in doc
    assert "OPERATOR_HANDOFF_MVP.md" in doc
    assert "LAUNCH_CHECKLIST.md" in doc
    assert "first_tenant_onboarded_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 33 F1" in readme
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in readme
    assert "first-tenant-onboarding.json" in readme


def test_f1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_33_PLAN.md")
    f1_line = [ln for ln in plan.splitlines() if "| **F1** |" in ln][0]
    assert "COMPLETE" in f1_line
    assert "test_first_tenant_onboarding_f1.py" in plan
    assert (
        "F1 next" in plan
        or "F1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H33x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_first_tenant_onboarding_f1.py" in launch
    assert "Stage 33 F1" in launch
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 33 F1" in roadmap
    assert "test_first_tenant_onboarding_f1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 33 F1" in pr
    assert "test_first_tenant_onboarding_f1.py" in pr or "FIRST_TENANT_ONBOARDING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "33",
        "workstream": "F1",
        "passed": True,
        "doc": "docs/FIRST_TENANT_ONBOARDING_MVP.md",
        "register": "ops/mvp/first-tenant-onboarding.json",
        "packaging_complete": True,
        "first_tenant_onboarded_claimed": False,
        "live_onboarding_success_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["first_tenant_onboarded_claimed"] is False
    assert loaded["live_onboarding_success_claimed"] is False
    assert loaded["step_count"] >= 10
