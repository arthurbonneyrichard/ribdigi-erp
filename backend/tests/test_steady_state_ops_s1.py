"""Stage 71 S1 — Steady-state commercial ops honesty (not steady-state live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "steady-state-ops.json"
FIRST_DAY = ROOT / "ops" / "mvp" / "first-commercial-day.json"
CONTINUITY = ROOT / "ops" / "mvp" / "post-launch-continuity.json"
CLOSEOUT = ROOT / "ops" / "mvp" / "commercial-golive-closeout.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage71_s1_steady_state_ops.json"

REQUIRED_IDS = {
    "sso-owner-outline",
    "sso-first-day",
    "sso-closeout",
    "sso-continuity",
    "sso-hypercare",
    "sso-handoff",
    "sso-support-sla",
    "sso-plan-honesty",
    "sso-steady-remaining",
    "sso-golive-remaining",
}
REQUIRED_CATEGORIES = {"steady_state", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_steady_state_ops_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "71"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["steady_state_ops_claimed"] is False
    assert mapping["commercial_acceptance_claimed"] is False
    assert mapping["first_commercial_day_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/STEADY_STATE_OPS_MVP.md"
    assert "stage71_s1_steady_state_ops.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sso-steady-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sso-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "steady" in d.lower() or "accept" in d.lower() or "go-live" in d.lower() or "first" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage71_plan"],
        mapping["first_commercial_day_doc"],
        mapping["first_commercial_day"],
        mapping["closeout_doc"],
        mapping["closeout"],
        mapping["continuity_doc"],
        mapping["continuity"],
        mapping["hypercare_doc"],
        mapping["hypercare"],
        mapping["handoff_doc"],
        mapping["handoff"],
        mapping["support_sla_doc"],
        mapping["support_sla"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_steady_state_ops_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    first_day = json.loads(FIRST_DAY.read_text(encoding="utf-8"))
    continuity = json.loads(CONTINUITY.read_text(encoding="utf-8"))
    closeout = json.loads(CLOSEOUT.read_text(encoding="utf-8"))
    assert mapping["steady_state_ops_claimed"] is False
    assert mapping["go_live_claimed"] is False
    for key in ("first_commercial_day_claimed", "go_live_claimed", "section_7_signed"):
        if key in first_day:
            assert first_day[key] is False
    for key in ("post_launch_continuity_live_claimed", "go_live_claimed", "handoff_complete_claimed"):
        if key in continuity:
            assert continuity[key] is False
    for key in ("go_live_claimed", "commercial_golive_closeout_claimed", "section_7_signed"):
        if key in closeout:
            assert closeout[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_71_PLAN.md")
    assert "Steady-State" in plan
    assert "Acceptance" in plan or "acceptance" in plan.lower()


def test_steady_state_ops_doc_and_readme():
    doc = _read("docs/STEADY_STATE_OPS_MVP.md")
    assert "Stage 71 S1" in doc
    assert "test_steady_state_ops_s1.py" in doc
    assert "steady-state-ops.json" in doc
    assert "steady_state_ops_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 71 S1" in readme
    assert "STEADY_STATE_OPS_MVP.md" in readme
    assert "steady-state-ops.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_71_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_steady_state_ops_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H71x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_steady_state_ops_s1.py" in launch
    assert "Stage 71 S1" in launch
    assert "STEADY_STATE_OPS_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 71 S1" in roadmap
    assert "test_steady_state_ops_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 71 S1" in pr
    assert "test_steady_state_ops_s1.py" in pr or "STEADY_STATE_OPS_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "71",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/STEADY_STATE_OPS_MVP.md",
        "register": "ops/mvp/steady-state-ops.json",
        "packaging_complete": True,
        "steady_state_ops_claimed": False,
        "commercial_acceptance_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["steady_state_ops_claimed"] is False
    assert loaded["step_count"] >= 10
