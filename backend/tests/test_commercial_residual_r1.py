"""Stage 72 R1 — Commercial residual remaining honesty (not residual closed Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-residual.json"
RESIDUAL = ROOT / "ops" / "mvp" / "residual-risk-register.json"
STEADY = ROOT / "ops" / "mvp" / "steady-state-ops.json"
ACCEPT = ROOT / "ops" / "mvp" / "commercial-acceptance.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage72_r1_commercial_residual.json"

REQUIRED_IDS = {
    "cr-owner-outline", "cr-residual-risk", "cr-operator-remaining", "cr-steady-state",
    "cr-acceptance", "cr-backlog", "cr-billing", "cr-plan-honesty",
    "cr-residual-remaining", "cr-golive-remaining",
}
REQUIRED_CATEGORIES = {"residual", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_residual_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "72" and mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    for k in ("residual_closed_claimed", "packaging_archive_live_claimed", "commercial_acceptance_claimed",
              "steady_state_ops_claimed", "go_live_claimed", "section_7_signed"):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_RESIDUAL_MVP.md"
    assert "stage72_r1_commercial_residual.json" in mapping["evidence_artifact"]
    steps = mapping["steps"]
    assert len(steps) >= 10
    assert REQUIRED_IDS.issubset({s["id"] for s in steps})
    assert REQUIRED_CATEGORIES.issubset({s["category"] for s in steps})
    for step in steps:
        assert step["done"] is False
        assert step["status"] in ("packaged", "remaining")
        assert step["title"] and step["source"] and step["pack_refs"]
        for pack in step["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(s["id"] == "cr-residual-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cr-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any("residual" in d.lower() or "accept" in d.lower() or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (mapping["stage72_plan"], mapping["residual_doc"], mapping["residual"],
                mapping["operator_remaining_doc"], mapping["operator_remaining"],
                mapping["steady_state_doc"], mapping["steady_state"],
                mapping["acceptance_doc"], mapping["acceptance"],
                mapping["backlog_doc"], mapping["backlog"],
                mapping["billing_doc"], mapping["billing"], mapping["launch_checklist"]):
        assert (ROOT / rel).is_file(), rel


def test_commercial_residual_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    steady = json.loads(STEADY.read_text(encoding="utf-8"))
    accept = json.loads(ACCEPT.read_text(encoding="utf-8"))
    assert mapping["residual_closed_claimed"] is False
    for key in ("risks_closed_claimed",):
        if key in residual:
            assert residual[key] is False
    for key in ("steady_state_ops_claimed", "go_live_claimed"):
        if key in steady:
            assert steady[key] is False
    for key in ("commercial_acceptance_claimed", "go_live_claimed"):
        if key in accept:
            assert accept[key] is False
    plan = _read("docs/STAGE_72_PLAN.md")
    assert "Residual" in plan and ("Archive" in plan or "Packaging" in plan)


def test_commercial_residual_doc_and_readme():
    doc = _read("docs/COMMERCIAL_RESIDUAL_MVP.md")
    assert "Stage 72 R1" in doc and "test_commercial_residual_r1.py" in doc
    assert "commercial-residual.json" in doc and "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 72 R1" in readme and "COMMERCIAL_RESIDUAL_MVP.md" in readme and "commercial-residual.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_72_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "test_commercial_residual_r1.py" in plan
    assert any(x in plan for x in ("R1 next", "R1 complete", "P1 next", "P1 complete", "D1 next", "D1 complete", "H72x next", "Closed", "exit met"))
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_residual_r1.py" in launch and "Stage 72 R1" in launch and "COMMERCIAL_RESIDUAL_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 72 R1" in roadmap and "test_commercial_residual_r1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 72 R1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"stage": "72", "workstream": "R1", "passed": True, "doc": "docs/COMMERCIAL_RESIDUAL_MVP.md",
               "register": "ops/mvp/commercial-residual.json", "packaging_complete": True,
               "residual_closed_claimed": False, "go_live_claimed": False,
               "step_count": len(mapping["steps"]), "deferred": mapping["deferred"]}
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["residual_closed_claimed"] is False
    assert loaded["step_count"] >= 10
