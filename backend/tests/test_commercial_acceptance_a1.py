"""Stage 71 A1 — Commercial acceptance gate honesty (not acceptance Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-acceptance.json"
GATE = ROOT / "ops" / "mvp" / "gate-matrix.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
STEADY = ROOT / "ops" / "mvp" / "steady-state-ops.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage71_a1_commercial_acceptance.json"

REQUIRED_IDS = {
    "ca-owner-outline",
    "ca-gate-matrix",
    "ca-mvp-declaration",
    "ca-steady-state",
    "ca-closeout",
    "ca-first-day",
    "ca-attestation",
    "ca-plan-honesty",
    "ca-acceptance-remaining",
    "ca-golive-remaining",
}
REQUIRED_CATEGORIES = {"acceptance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_acceptance_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "71"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["commercial_acceptance_claimed"] is False
    assert mapping["steady_state_ops_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["first_commercial_day_claimed"] is False
    assert mapping["doc"] == "docs/COMMERCIAL_ACCEPTANCE_MVP.md"
    assert "stage71_a1_commercial_acceptance.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ca-acceptance-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ca-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "accept" in d.lower() or "go-live" in d.lower() or "steady" in d.lower() or "section" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage71_plan"],
        mapping["gate_matrix_doc"],
        mapping["gate_matrix"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["steady_state_doc"],
        mapping["steady_state"],
        mapping["closeout_doc"],
        mapping["closeout"],
        mapping["first_commercial_day_doc"],
        mapping["first_commercial_day"],
        mapping["golive_attestation_doc"],
        mapping["golive_attestation"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_commercial_acceptance_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    steady = json.loads(STEADY.read_text(encoding="utf-8"))
    assert mapping["commercial_acceptance_claimed"] is False
    assert mapping["go_live_claimed"] is False
    for key in ("go_live_claimed", "section_7_signed"):
        if key in gate:
            assert gate[key] is False
    for key in ("go_live_claimed", "section_7_signed", "attestation_claimed"):
        if key in mvp:
            assert mvp[key] is False
    for key in ("steady_state_ops_claimed", "go_live_claimed", "commercial_acceptance_claimed"):
        if key in steady:
            assert steady[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_71_PLAN.md")
    assert "Acceptance" in plan or "acceptance" in plan.lower()
    assert "Steady-State" in plan


def test_commercial_acceptance_doc_and_readme():
    doc = _read("docs/COMMERCIAL_ACCEPTANCE_MVP.md")
    assert "Stage 71 A1" in doc
    assert "test_commercial_acceptance_a1.py" in doc
    assert "commercial-acceptance.json" in doc
    assert "commercial_acceptance_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 71 A1" in readme
    assert "COMMERCIAL_ACCEPTANCE_MVP.md" in readme
    assert "commercial-acceptance.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_71_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_commercial_acceptance_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H71x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_acceptance_a1.py" in launch
    assert "Stage 71 A1" in launch
    assert "COMMERCIAL_ACCEPTANCE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 71 A1" in roadmap
    assert "test_commercial_acceptance_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 71 A1" in pr
    assert "test_commercial_acceptance_a1.py" in pr or "COMMERCIAL_ACCEPTANCE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "71",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/COMMERCIAL_ACCEPTANCE_MVP.md",
        "register": "ops/mvp/commercial-acceptance.json",
        "packaging_complete": True,
        "commercial_acceptance_claimed": False,
        "steady_state_ops_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["commercial_acceptance_claimed"] is False
    assert loaded["step_count"] >= 10
