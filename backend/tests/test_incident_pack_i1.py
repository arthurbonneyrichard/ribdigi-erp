"""Stage 30 I1 — incident response / on-call pack (not hosted PagerDuty Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "incident" / "incident-checklist.json"
RUNBOOK = ROOT / "ops" / "incident" / "oncall-runbook.md.example"
ALERTMANAGER = ROOT / "ops" / "grafana" / "alertmanager.yml.example"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/monitoring")
EVIDENCE_FILE = EVIDENCE_DIR / "stage30_i1_incident_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_incident_checklist_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "30"
    assert mapping["workstream"] == "I1"
    assert mapping["pagerduty_hosted_claimed"] is False
    assert mapping["oncall_rota_live"] is False
    assert mapping["incident_drill_executed"] is False
    assert mapping["doc"] == "docs/INCIDENT_PACK_MVP.md"
    assert mapping["ops_monitoring_mvp"] == "docs/OPS_MONITORING_MVP.md"
    assert mapping["grafana_pack_mvp"] == "docs/GRAFANA_PACK_MVP.md"
    assert mapping["alertmanager"] == "ops/grafana/alertmanager.yml.example"
    assert mapping["runbook"] == "ops/incident/oncall-runbook.md.example"
    assert len(mapping["severity_levels"]) >= 4
    assert {s["id"] for s in mapping["severity_levels"]} >= {"P1", "P2", "P3", "P4"}
    assert len(mapping["steps"]) >= 4
    for step in mapping["steps"]:
        assert step["class"] == "operator_required"
    assert "stage30_i1_incident_pack.json" in mapping["evidence_artifact"]
    assert any(
        "PagerDuty" in d or "SIEM" in d or "rota" in d.lower() or "drill" in d.lower()
        for d in mapping["deferred"]
    )


def test_oncall_runbook_and_alertmanager_still_honest():
    assert RUNBOOK.is_file()
    rb = RUNBOOK.read_text(encoding="utf-8")
    assert "Stage 30 I1" in rb or "INCIDENT_PACK_MVP" in rb
    assert "NOT" in rb or "not" in rb.lower()
    assert "RibdigiDown" in rb or "NotReady" in rb
    assert "Contain" in rb or "Containment" in rb
    assert "PagerDuty" in rb or "pagerduty" in rb.lower()
    assert "health/ready" in rb or "/api/v1/health" in rb
    assert "SECURITY_GUIDE" in rb or "§15" in rb

    assert ALERTMANAGER.is_file()
    am = ALERTMANAGER.read_text(encoding="utf-8")
    assert "# pagerduty_configs" in am or "#   - routing_key" in am
    assert "critical" in am.lower()


def test_incident_pack_mvp_doc_and_security_guide():
    doc = _read("docs/INCIDENT_PACK_MVP.md")
    assert "Stage 30 I1" in doc
    assert "test_incident_pack_i1.py" in doc
    assert "incident-checklist.json" in doc
    assert "oncall-runbook.md.example" in doc
    assert "GRAFANA_PACK_MVP.md" in doc
    assert "OPS_MONITORING_MVP.md" in doc
    assert "not" in doc.lower()
    assert "stage30_i1_incident_pack.json" in doc

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 30 I1" in sec
    assert "INCIDENT_PACK_MVP.md" in sec or "test_incident_pack_i1.py" in sec
    assert "## 15. Incident Response Plan" in sec

    readme = _read("ops/incident/README.md")
    assert "Stage 30 I1" in readme
    assert "INCIDENT_PACK_MVP.md" in readme

    grafana = _read("docs/GRAFANA_PACK_MVP.md")
    assert "Stage 30 I1" in grafana or "INCIDENT_PACK_MVP.md" in grafana


def test_i1_plan_launch_roadmap_deploy_readiness():
    plan = _read("docs/STAGE_30_PLAN.md")
    i1_line = [ln for ln in plan.splitlines() if "| **I1** |" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_incident_pack_i1.py" in plan
    assert (
        "I1 next" in plan
        or "I1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H30x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_incident_pack_i1.py" in launch
    assert "Stage 30 I1" in launch
    assert "INCIDENT_PACK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 30 I1" in roadmap
    assert "test_incident_pack_i1.py" in roadmap

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 30 I1" in deploy or "INCIDENT_PACK_MVP.md" in deploy
    assert "test_incident_pack_i1.py" in deploy or "oncall-runbook" in deploy

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 30 I1" in pr
    assert "test_incident_pack_i1.py" in pr or "INCIDENT_PACK_MVP.md" in pr
    mon_gate = pr.split("- [x] Monitoring, metrics, logging and alerting complete.")[1].split("- [x]")[0]
    assert "Stage 30 I1" in mon_gate or "INCIDENT" in mon_gate or "incident" in mon_gate.lower()
    assert (
        "Remaining" in mon_gate
        or "PagerDuty" in mon_gate
        or "hosted" in mon_gate.lower()
        or "rota" in mon_gate.lower()
    )

    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "30",
        "workstream": "I1",
        "passed": True,
        "doc": "docs/INCIDENT_PACK_MVP.md",
        "checklist": "ops/incident/incident-checklist.json",
        "runbook": "ops/incident/oncall-runbook.md.example",
        "alertmanager": "ops/grafana/alertmanager.yml.example",
        "pagerduty_hosted_claimed": False,
        "oncall_rota_live": False,
        "incident_drill_executed": False,
        "packaging_complete": True,
        "steps": mapping["steps"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["pagerduty_hosted_claimed"] is False
    assert loaded["oncall_rota_live"] is False
    assert loaded["incident_drill_executed"] is False
    assert loaded["packaging_complete"] is True
