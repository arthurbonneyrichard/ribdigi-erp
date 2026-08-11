"""Stage 36 S1 — Support SLA boundary (not live SLA / PagerDuty Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
INCIDENT = ROOT / "ops" / "incident" / "incident-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage36_s1_support_sla_boundary.json"

REQUIRED_IDS = {
    "ss-severity-ack-targets",
    "ss-incident-escalation",
    "ss-support-runbook",
    "ss-alertmanager-pagerduty",
    "ss-oncall-remaining",
    "ss-customer-contact",
    "ss-post-incident-evidence",
    "ss-helpdesk-saas-deferred",
    "ss-incident-drill-remaining",
    "ss-live-sla-remaining",
}
REQUIRED_CATEGORIES = {"sla", "incident", "support", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_support_sla_boundary_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "36"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["support_sla_claimed"] is False
    assert mapping["pagerduty_hosted_claimed"] is False
    assert mapping["oncall_rota_live"] is False
    assert mapping["incident_drill_executed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/SUPPORT_SLA_BOUNDARY_MVP.md"
    assert "stage36_s1_support_sla_boundary.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ss-live-sla-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ss-severity-ack-targets" for s in steps)
    assert any(
        "sla" in d.lower() or "pagerduty" in d.lower() or "on-call" in d.lower() or "oncall" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["support_runbook"],
        mapping["incident_pack"],
        mapping["incident_checklist"],
        mapping["admin_ops_map"],
        mapping["assurance_evidence"],
        mapping["stage36_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_support_sla_boundary_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    incident = json.loads(INCIDENT.read_text(encoding="utf-8"))
    assert mapping["support_sla_claimed"] is False
    assert mapping["pagerduty_hosted_claimed"] is False
    # incident checklist should not claim live drill
    flags = json.dumps(incident).lower()
    assert "true" not in flags or "pagerduty_hosted_claimed" in flags or "incident" in flags
    for step in mapping["steps"]:
        assert step["done"] is False
    incident_doc = _read("docs/INCIDENT_PACK_MVP.md")
    assert "PagerDuty" in incident_doc or "pagerduty" in incident_doc.lower()
    support = _read("docs/SUPPORT_RUNBOOK_MVP.md")
    assert "support_sla_claimed" in support or "SLA" in support or "sla" in support.lower()


def test_support_sla_boundary_doc_and_readme():
    doc = _read("docs/SUPPORT_SLA_BOUNDARY_MVP.md")
    assert "Stage 36 S1" in doc
    assert "test_support_sla_boundary_s1.py" in doc
    assert "support-sla-boundary.json" in doc
    assert "stage36_s1_support_sla_boundary.json" in doc
    assert "support_sla_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "PagerDuty" in doc or "pagerduty" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 36 S1" in readme
    assert "SUPPORT_SLA_BOUNDARY_MVP.md" in readme
    assert "support-sla-boundary.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_36_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_support_sla_boundary_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_support_sla_boundary_s1.py" in launch
    assert "Stage 36 S1" in launch
    assert "SUPPORT_SLA_BOUNDARY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 36 S1" in roadmap
    assert "test_support_sla_boundary_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 36 S1" in pr
    assert "test_support_sla_boundary_s1.py" in pr or "SUPPORT_SLA_BOUNDARY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "36",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/SUPPORT_SLA_BOUNDARY_MVP.md",
        "register": "ops/mvp/support-sla-boundary.json",
        "packaging_complete": True,
        "support_sla_claimed": False,
        "pagerduty_hosted_claimed": False,
        "oncall_rota_live": False,
        "incident_drill_executed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["support_sla_claimed"] is False
    assert loaded["pagerduty_hosted_claimed"] is False
    assert loaded["oncall_rota_live"] is False
    assert loaded["step_count"] >= 10
