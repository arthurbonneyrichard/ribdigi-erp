"""Stage 41 A1 — Accessibility statement honesty (not WCAG AA audit Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "accessibility-statement.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage41_a1_accessibility_statement.json"

REQUIRED_IDS = {
    "as-br-wcag-target",
    "as-roadmap-dod",
    "as-browser-responsive",
    "as-frontend-surface",
    "as-release-notes",
    "as-operator-handoff",
    "as-i18n-deferred",
    "as-onboarding-help",
    "as-wcag-audit-remaining",
    "as-conformance-remaining",
}
REQUIRED_CATEGORIES = {"accessibility", "usability", "frontend", "handoff", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_accessibility_statement_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "41"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["wcag_aa_claimed"] is False
    assert mapping["accessibility_audit_claimed"] is False
    assert mapping["conformance_program_live"] is False
    assert mapping["remediation_complete_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/ACCESSIBILITY_STATEMENT_MVP.md"
    assert "stage41_a1_accessibility_statement.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "as-wcag-audit-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "as-conformance-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "as-br-wcag-target" for s in steps)
    assert any(
        "wcag" in d.lower() or "accessibility" in d.lower() or "i18n" in d.lower() or "remediation" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["business_requirements"],
        mapping["development_roadmap"],
        mapping["release_notes"],
        mapping["release_notes_register"],
        mapping["operator_handoff"],
        mapping["operator_handoff_register"],
        mapping["frontend_package"],
        mapping["stage41_plan"],
        mapping["launch_checklist"],
        mapping["deferred_adr_register"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_accessibility_statement_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["wcag_aa_claimed"] is False
    assert mapping["accessibility_audit_claimed"] is False
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "WCAG" in br
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Accessibility" in roadmap or "WCAG" in roadmap
    assert "- [ ] Accessibility checked" in roadmap or "WCAG 2.1 AA" in roadmap
    for step in mapping["steps"]:
        assert step["done"] is False
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    blob = json.dumps(deferred).lower()
    assert "i18n" in blob or "adr-006" in blob or "006" in blob
    pkg = json.loads(_read("frontend/package.json"))
    assert "name" in pkg or "dependencies" in pkg


def test_accessibility_statement_doc_and_readme():
    doc = _read("docs/ACCESSIBILITY_STATEMENT_MVP.md")
    assert "Stage 41 A1" in doc
    assert "test_accessibility_statement_a1.py" in doc
    assert "accessibility-statement.json" in doc
    assert "stage41_a1_accessibility_statement.json" in doc
    assert "wcag_aa_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "WCAG" in doc or "accessibility" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 41 A1" in readme
    assert "ACCESSIBILITY_STATEMENT_MVP.md" in readme
    assert "accessibility-statement.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_41_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_accessibility_statement_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H41x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_accessibility_statement_a1.py" in launch
    assert "Stage 41 A1" in launch
    assert "ACCESSIBILITY_STATEMENT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 41 A1" in roadmap
    assert "test_accessibility_statement_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 41 A1" in pr
    assert "test_accessibility_statement_a1.py" in pr or "ACCESSIBILITY_STATEMENT_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "41",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/ACCESSIBILITY_STATEMENT_MVP.md",
        "register": "ops/mvp/accessibility-statement.json",
        "packaging_complete": True,
        "wcag_aa_claimed": False,
        "accessibility_audit_claimed": False,
        "conformance_program_live": False,
        "remediation_complete_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["wcag_aa_claimed"] is False
    assert loaded["accessibility_audit_claimed"] is False
    assert loaded["step_count"] >= 10
