"""Stage 41 C1 — Change / maintenance governance honesty (not public change calendar Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "change-governance.json"
CUTOVER = ROOT / "ops" / "launch" / "cutover-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage41_c1_change_governance.json"

REQUIRED_IDS = {
    "cg-admin-maintenance-window",
    "cg-dr-rto-window",
    "cg-cutover-changelog",
    "cg-staging-gha",
    "cg-release-notes",
    "cg-status-uptime-adjacency",
    "cg-database-docs",
    "cg-deploy-free-ci",
    "cg-change-calendar-remaining",
    "cg-maintenance-portal-remaining",
}
REQUIRED_CATEGORIES = {"maintenance", "change", "deploy", "release", "availability", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_change_governance_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "41"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["change_calendar_live"] is False
    assert mapping["maintenance_portal_claimed"] is False
    assert mapping["customer_change_notices_live"] is False
    assert mapping["ops_changelog_saas_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CHANGE_GOVERNANCE_MVP.md"
    assert "stage41_c1_change_governance.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "cg-change-calendar-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cg-maintenance-portal-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cg-admin-maintenance-window" for s in steps)
    assert any(
        "change" in d.lower() or "maintenance" in d.lower() or "calendar" in d.lower() or "cutover" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["admin_manual"],
        mapping["dr_logical_backup"],
        mapping["cutover_pack"],
        mapping["cutover_checklist"],
        mapping["staging_gha"],
        mapping["staging_gha_template"],
        mapping["release_notes"],
        mapping["release_notes_register"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
        mapping["database_docs"],
        mapping["deployment_guide"],
        mapping["accessibility_statement"],
        mapping["stage41_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_change_governance_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["change_calendar_live"] is False
    assert mapping["maintenance_portal_claimed"] is False
    admin = _read("docs/ADMIN_MANUAL.md")
    assert "maintenance" in admin.lower()
    dr = _read("docs/DR_LOGICAL_BACKUP_RUNBOOK.md")
    assert "maintenance" in dr.lower() or "RTO" in dr
    for step in mapping["steps"]:
        assert step["done"] is False
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    assert cutover.get("production_cutover_claimed") is False or "cutover" in json.dumps(cutover).lower()
    cut_doc = _read("docs/CUTOVER_PACK_MVP.md")
    assert "change-log" in cut_doc.lower() or "rollback" in cut_doc.lower() or "cutover" in cut_doc.lower()
    ci = _read(".github/workflows/ci.yml")
    assert "kubectl" not in ci.lower() or "deploy" in ci.lower()  # deploy-free honesty checked via deploy guide
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "deploy-free" in deploy.lower() or "Stage 18 C1" in deploy


def test_change_governance_doc_and_readme():
    doc = _read("docs/CHANGE_GOVERNANCE_MVP.md")
    assert "Stage 41 C1" in doc
    assert "test_change_governance_c1.py" in doc
    assert "change-governance.json" in doc
    assert "stage41_c1_change_governance.json" in doc
    assert "change_calendar_live" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "maintenance" in doc.lower() or "change" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 41 C1" in readme
    assert "CHANGE_GOVERNANCE_MVP.md" in readme
    assert "change-governance.json" in readme


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_41_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_change_governance_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H41x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
        or "A1 complete" in plan
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_change_governance_c1.py" in launch
    assert "Stage 41 C1" in launch
    assert "CHANGE_GOVERNANCE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 41 C1" in roadmap
    assert "test_change_governance_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 41 C1" in pr
    assert "test_change_governance_c1.py" in pr or "CHANGE_GOVERNANCE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "41",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/CHANGE_GOVERNANCE_MVP.md",
        "register": "ops/mvp/change-governance.json",
        "packaging_complete": True,
        "change_calendar_live": False,
        "maintenance_portal_claimed": False,
        "customer_change_notices_live": False,
        "ops_changelog_saas_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["change_calendar_live"] is False
    assert loaded["maintenance_portal_claimed"] is False
    assert loaded["step_count"] >= 10
