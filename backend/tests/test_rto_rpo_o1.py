"""Stage 45 O1 — RTO / RPO honesty (not measured RTO/RPO SLA Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "rto-rpo.json"
STATUS = ROOT / "ops" / "mvp" / "status-uptime.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage45_o1_rto_rpo.json"

REQUIRED_IDS = {
    "rr-br-rto",
    "rr-br-rpo",
    "rr-security-strategy",
    "rr-wal-pitr",
    "rr-pitr-drill",
    "rr-status-uptime",
    "rr-support-sla",
    "rr-change-governance",
    "rr-measured-remaining",
    "rr-failover-remaining",
}
REQUIRED_CATEGORIES = {"rto", "rpo", "availability", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_rto_rpo_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "45"
    assert mapping["workstream"] == "O1"
    assert mapping["packaging_complete"] is True
    assert mapping["measured_rto_claimed"] is False
    assert mapping["measured_rpo_claimed"] is False
    assert mapping["multi_region_failover_claimed"] is False
    assert mapping["rto_rpo_sla_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/RTO_RPO_MVP.md"
    assert "stage45_o1_rto_rpo.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "rr-measured-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "rr-failover-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "rr-br-rto" for s in steps)
    assert any(
        "rto" in d.lower() or "rpo" in d.lower() or "failover" in d.lower() or "drill" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["business_requirements"],
        mapping["security_guide"],
        mapping["wal_pitr_doc"],
        mapping["pitr_drill_doc"],
        mapping["pitr_checklist"],
        mapping["status_uptime"],
        mapping["status_uptime_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["change_governance"],
        mapping["change_governance_doc"],
        mapping["incident_pack_doc"],
        mapping["incident_checklist"],
        mapping["logical_backup_doc"],
        mapping["stage45_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_rto_rpo_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    assert mapping["measured_rto_claimed"] is False
    assert mapping["measured_rpo_claimed"] is False
    assert status.get("uptime_sla_claimed") is False
    assert status.get("measured_uptime_claimed") is False
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "RTO" in br and "RPO" in br
    for step in mapping["steps"]:
        assert step["done"] is False
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "RTO" in sec or "RPO" in sec or "PITR" in sec
    wal = _read("docs/DR_WAL_PITR_RUNBOOK.md")
    assert "RTO" in wal or "RPO" in wal or "PITR" in wal or "WAL" in wal


def test_rto_rpo_doc_and_readme():
    doc = _read("docs/RTO_RPO_MVP.md")
    assert "Stage 45 O1" in doc
    assert "test_rto_rpo_o1.py" in doc
    assert "rto-rpo.json" in doc
    assert "stage45_o1_rto_rpo.json" in doc
    assert "measured_rto_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "RTO" in doc or "RPO" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 45 O1" in readme
    assert "RTO_RPO_MVP.md" in readme
    assert "rto-rpo.json" in readme


def test_o1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_45_PLAN.md")
    o1_line = [ln for ln in plan.splitlines() if "| **O1** |" in ln][0]
    assert "COMPLETE" in o1_line
    assert "test_rto_rpo_o1.py" in plan
    assert (
        "O1 next" in plan
        or "O1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H45x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_rto_rpo_o1.py" in launch
    assert "Stage 45 O1" in launch
    assert "RTO_RPO_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 45 O1" in roadmap
    assert "test_rto_rpo_o1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 45 O1" in pr
    assert "test_rto_rpo_o1.py" in pr or "RTO_RPO_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "45",
        "workstream": "O1",
        "passed": True,
        "doc": "docs/RTO_RPO_MVP.md",
        "register": "ops/mvp/rto-rpo.json",
        "packaging_complete": True,
        "measured_rto_claimed": False,
        "measured_rpo_claimed": False,
        "multi_region_failover_claimed": False,
        "rto_rpo_sla_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["measured_rto_claimed"] is False
    assert loaded["measured_rpo_claimed"] is False
    assert loaded["step_count"] >= 10
