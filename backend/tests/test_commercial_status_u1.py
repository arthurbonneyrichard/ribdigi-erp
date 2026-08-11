"""Stage 74 U1 — Commercial status boundary honesty (not status page live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-status.json"
STATUS = ROOT / "ops" / "mvp" / "status-uptime.json"
SUPPORT = ROOT / "ops" / "mvp" / "commercial-support.json"
ASSURE = ROOT / "ops" / "mvp" / "commercial-assurance.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage74_u1_commercial_status.json"

REQUIRED_IDS = {
    "cst-owner-outline", "cst-status-uptime", "cst-support", "cst-assurance", "cst-evidence-chain",
    "cst-monitoring", "cst-support-sla", "cst-plan-honesty", "cst-status-remaining", "cst-golive-remaining",
}
REQUIRED_CATEGORIES = {"status", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_status_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "74" and mapping["workstream"] == "U1"
    assert mapping["packaging_complete"] is True
    for k in ("status_page_live", "uptime_sla_claimed", "measured_uptime_claimed",
              "commercial_support_claimed", "customer_assurance_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_STATUS_MVP.md"
    assert "stage74_u1_commercial_status.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cst-status-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cst-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("status" in d.lower() or "uptime" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage74_plan"], mapping["status_uptime_doc"], mapping["status_uptime"],
                mapping["support_doc"], mapping["support"], mapping["assurance_doc"], mapping["assurance"],
                mapping["evidence_chain_doc"], mapping["evidence_chain"], mapping["ops_monitoring_doc"],
                mapping["support_sla_doc"], mapping["support_sla"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_status_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT.read_text(encoding="utf-8"))
    assure = json.loads(ASSURE.read_text(encoding="utf-8"))
    assert mapping["status_page_live"] is False
    for key in ("status_page_live", "uptime_sla_claimed", "measured_uptime_claimed"):
        if key in status:
            assert status[key] is False
    for key in ("commercial_support_claimed", "support_boundary_live_claimed", "go_live_claimed"):
        if key in support:
            assert support[key] is False
    for key in ("customer_assurance_claimed", "go_live_claimed"):
        if key in assure:
            assert assure[key] is False
    plan = _read("docs/STAGE_74_PLAN.md")
    assert "Status" in plan and "Support" in plan


def test_commercial_status_doc_and_readme():
    doc = _read("docs/COMMERCIAL_STATUS_MVP.md")
    assert "Stage 74 U1" in doc and "test_commercial_status_u1.py" in doc
    assert "commercial-status.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 74 U1" in readme and "COMMERCIAL_STATUS_MVP.md" in readme and "commercial-status.json" in readme


def test_u1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_74_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **U1** |" in ln][0]
    assert "test_commercial_status_u1.py" in plan
    assert any(x in plan for x in ("U1 next", "U1 complete", "D1 next", "D1 complete", "H74x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_status_u1.py" in launch and "Stage 74 U1" in launch and "COMMERCIAL_STATUS_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 74 U1" in roadmap and "test_commercial_status_u1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 74 U1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "74", "workstream": "U1", "passed": True, "doc": "docs/COMMERCIAL_STATUS_MVP.md",
               "register": "ops/mvp/commercial-status.json", "packaging_complete": True,
               "status_page_live": False, "uptime_sla_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["status_page_live"] is False and loaded["step_count"] >= 10
