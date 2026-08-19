"""Stage 74 S1 — Commercial support boundary honesty (not support boundary live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-support.json"
SLA = ROOT / "ops" / "mvp" / "support-sla-boundary.json"
ASSURE = ROOT / "ops" / "mvp" / "commercial-assurance.json"
HYPER = ROOT / "ops" / "mvp" / "production-hypercare.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage74_s1_commercial_support.json"

REQUIRED_IDS = {
    "cs-owner-outline", "cs-support-sla", "cs-runbook", "cs-incident", "cs-assurance",
    "cs-hypercare", "cs-handoff", "cs-plan-honesty", "cs-support-remaining", "cs-golive-remaining",
}
REQUIRED_CATEGORIES = {"support", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_support_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "74" and mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    for k in ("commercial_support_claimed", "support_boundary_live_claimed", "support_sla_claimed",
              "status_page_live", "customer_assurance_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_SUPPORT_MVP.md"
    assert "stage74_s1_commercial_support.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False and step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cs-support-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cs-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("support" in d.lower() or "status" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage74_plan"], mapping["support_sla_doc"], mapping["support_sla"],
                mapping["support_runbook_doc"], mapping["incident_doc"], mapping["incident_checklist"],
                mapping["assurance_doc"], mapping["assurance"], mapping["hypercare_doc"], mapping["hypercare"],
                mapping["handoff_doc"], mapping["handoff"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_support_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    sla = json.loads(SLA.read_text(encoding="utf-8"))
    assure = json.loads(ASSURE.read_text(encoding="utf-8"))
    hyper = json.loads(HYPER.read_text(encoding="utf-8"))
    assert mapping["commercial_support_claimed"] is False
    for key in ("support_sla_claimed", "go_live_claimed"):
        if key in sla:
            assert sla[key] is False
    for key in ("customer_assurance_claimed", "go_live_claimed"):
        if key in assure:
            assert assure[key] is False
    for key in ("production_hypercare_live_claimed", "support_sla_claimed"):
        if key in hyper:
            assert hyper[key] is False
    plan = _read("docs/STAGE_74_PLAN.md")
    assert "Support" in plan and "Status" in plan


def test_commercial_support_doc_and_readme():
    doc = _read("docs/COMMERCIAL_SUPPORT_MVP.md")
    assert "Stage 74 S1" in doc and "test_commercial_support_s1.py" in doc
    assert "commercial-support.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 74 S1" in readme and "COMMERCIAL_SUPPORT_MVP.md" in readme and "commercial-support.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_74_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "test_commercial_support_s1.py" in plan
    assert any(x in plan for x in ("S1 next", "S1 complete", "U1 next", "U1 complete", "D1 next", "D1 complete", "H74x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_support_s1.py" in launch and "Stage 74 S1" in launch and "COMMERCIAL_SUPPORT_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 74 S1" in roadmap and "test_commercial_support_s1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 74 S1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "74", "workstream": "S1", "passed": True, "doc": "docs/COMMERCIAL_SUPPORT_MVP.md",
               "register": "ops/mvp/commercial-support.json", "packaging_complete": True,
               "commercial_support_claimed": False, "support_boundary_live_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True and loaded["commercial_support_claimed"] is False and loaded["step_count"] >= 10
