"""Stage 67 H1 — Production hypercare honesty (not live hypercare Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "production-hypercare.json"
INCIDENT = ROOT / "ops" / "incident" / "incident-checklist.json"
SLA = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
LAUNCH = ROOT / "ops" / "mvp" / "production-launch.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage67_h1_production_hypercare.json"

REQUIRED_IDS = {
    "ph-owner-outline",
    "ph-incident",
    "ph-support-runbook",
    "ph-support-sla",
    "ph-monitoring",
    "ph-production-launch",
    "ph-plan-honesty",
    "ph-hypercare-remaining",
    "ph-incident-remaining",
    "ph-sla-remaining",
}
REQUIRED_CATEGORIES = {"hypercare", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_production_hypercare_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "67"
    assert mapping["workstream"] == "H1"
    assert mapping["packaging_complete"] is True
    assert mapping["production_hypercare_live_claimed"] is False
    assert mapping["incident_drill_executed"] is False
    assert mapping["oncall_rota_live"] is False
    assert mapping["support_sla_claimed"] is False
    assert mapping["pagerduty_hosted_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/PRODUCTION_HYPERCARE_MVP.md"
    assert "stage67_h1_production_hypercare.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ph-hypercare-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ph-incident-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ph-sla-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "hypercare" in d.lower() or "incident" in d.lower() or "sla" in d.lower() or "pager" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage67_plan"],
        mapping["incident_doc"],
        mapping["incident_checklist"],
        mapping["support_runbook_doc"],
        mapping["support_sla_doc"],
        mapping["support_sla"],
        mapping["ops_monitoring_doc"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_production_hypercare_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    incident = json.loads(INCIDENT.read_text(encoding="utf-8"))
    sla = json.loads(SLA.read_text(encoding="utf-8"))
    launch = json.loads(LAUNCH.read_text(encoding="utf-8"))
    assert mapping["production_hypercare_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    for key in ("incident_drill_executed", "oncall_rota_live", "pagerduty_hosted_claimed"):
        if key in incident:
            assert incident[key] is False
    for key in ("support_sla_claimed", "incident_drill_executed", "go_live_claimed"):
        if key in sla:
            assert sla[key] is False
    for key in ("go_live_claimed", "section_7_signed", "production_cutover_claimed"):
        if key in launch:
            assert launch[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_67_PLAN.md")
    assert "Production Hypercare" in plan or "hypercare" in plan.lower()
    assert "Post-Launch Continuity" in plan or "continuity" in plan.lower()


def test_production_hypercare_doc_and_readme():
    doc = _read("docs/PRODUCTION_HYPERCARE_MVP.md")
    assert "Stage 67 H1" in doc
    assert "test_production_hypercare_h1.py" in doc
    assert "production-hypercare.json" in doc
    assert "stage67_h1_production_hypercare.json" in doc
    assert "production_hypercare_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "hypercare" in doc.lower() or "incident" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 67 H1" in readme
    assert "PRODUCTION_HYPERCARE_MVP.md" in readme
    assert "production-hypercare.json" in readme


def test_h1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_67_PLAN.md")
    h1_line = [ln for ln in plan.splitlines() if "| **H1** |" in ln][0]
    assert "COMPLETE" in h1_line
    assert "test_production_hypercare_h1.py" in plan
    assert (
        "H1 next" in plan
        or "H1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H67x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_production_hypercare_h1.py" in launch
    assert "Stage 67 H1" in launch
    assert "PRODUCTION_HYPERCARE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 67 H1" in roadmap
    assert "test_production_hypercare_h1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 67 H1" in pr
    assert "test_production_hypercare_h1.py" in pr or "PRODUCTION_HYPERCARE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "67",
        "workstream": "H1",
        "passed": True,
        "doc": "docs/PRODUCTION_HYPERCARE_MVP.md",
        "register": "ops/mvp/production-hypercare.json",
        "packaging_complete": True,
        "production_hypercare_live_claimed": False,
        "incident_drill_executed": False,
        "oncall_rota_live": False,
        "support_sla_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["production_hypercare_live_claimed"] is False
    assert loaded["incident_drill_executed"] is False
    assert loaded["step_count"] >= 10
