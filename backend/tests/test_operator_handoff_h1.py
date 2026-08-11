"""Stage 32 H1 — operator handoff pack (not forged live runs / §7)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "ops" / "mvp" / "operator-handoff.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
DECLARATION = ROOT / "ops" / "mvp" / "mvp-declaration.json"
ARCHIVE = ROOT / "ops" / "mvp" / "acceptance-archive.json"
CUTOVER = ROOT / "ops" / "launch" / "cutover-checklist.json"
ATTESTATION = ROOT / "ops" / "launch" / "attestation-matrix.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage32_h1_operator_handoff.json"

REQUIRED_PHASE_IDS = {"1", "2", "3", "4", "5", "6", "7", "8"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_operator_handoff_honest():
    assert HANDOFF.is_file()
    mapping = json.loads(HANDOFF.read_text(encoding="utf-8"))
    assert mapping["stage"] == "32"
    assert mapping["workstream"] == "H1"
    assert mapping["handoff_complete_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["doc"] == "docs/OPERATOR_HANDOFF_MVP.md"
    assert mapping["operator_remaining_register"] == "ops/mvp/operator-remaining-register.json"
    assert mapping["mvp_declaration"] == "ops/mvp/mvp-declaration.json"
    assert mapping["acceptance_archive"] == "ops/mvp/acceptance-archive.json"
    assert mapping["cutover_checklist"] == "ops/launch/cutover-checklist.json"
    assert "stage32_h1_operator_handoff.json" in mapping["evidence_artifact"]
    phases = mapping["phases"]
    assert len(phases) >= 8
    ids = {p["id"] for p in phases}
    assert REQUIRED_PHASE_IDS.issubset(ids)
    for phase in phases:
        assert phase["class"] == "operator_required"
        assert phase["done"] is False
        assert phase["title"]
        assert phase["pack_refs"]
        for ref in phase["pack_refs"]:
            assert (ROOT / ref).is_file(), ref
    assert any("§7" in c or "Remaining" in c or "deploy-free" in c for c in mapping["pass_criteria"])
    assert any("§7" in d or "live" in d.lower() or "Remaining" in d for d in mapping["deferred"])


def test_operator_handoff_aligns_sources():
    mapping = json.loads(HANDOFF.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))

    assert remaining["live_runs_certified"] is False
    assert remaining["attestation_claimed"] is False
    assert remaining["section_7_signed"] is False
    assert declaration["go_live_claimed"] is False
    assert declaration["section_7_signed"] is False
    assert declaration["packaging_complete"] is True
    assert archive["go_live_claimed"] is False
    assert archive["archive_complete"] is True
    assert cutover["production_cutover_claimed"] is False
    assert cutover["section_7_signed"] is False
    assert attestation["attestation_claimed"] is False
    assert attestation["section_7_signed"] is False

    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["handoff_complete_claimed"] is False


def test_operator_handoff_doc_and_readme():
    doc = _read("docs/OPERATOR_HANDOFF_MVP.md")
    assert "Stage 32 H1" in doc
    assert "test_operator_handoff_h1.py" in doc
    assert "operator-handoff.json" in doc
    assert "stage32_h1_operator_handoff.json" in doc
    assert "OPERATOR_REMAINING_MVP.md" in doc
    assert "CUTOVER_PACK_MVP.md" in doc or "cutover" in doc.lower()
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 32 H1" in readme
    assert "OPERATOR_HANDOFF_MVP.md" in readme
    assert "operator-handoff.json" in readme


def test_h1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_32_PLAN.md")
    h1_line = [ln for ln in plan.splitlines() if "| **H1** |" in ln][0]
    assert "COMPLETE" in h1_line
    assert "test_operator_handoff_h1.py" in plan
    assert (
        "H1 next" in plan
        or "H1 complete" in plan
        or "N1 next" in plan
        or "N1 complete" in plan
        or "B1 next" in plan
        or "D1 next" in plan
        or "H32x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_operator_handoff_h1.py" in launch
    assert "Stage 32 H1" in launch
    assert "OPERATOR_HANDOFF_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 32 H1" in roadmap
    assert "test_operator_handoff_h1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 32 H1" in pr
    assert "test_operator_handoff_h1.py" in pr or "OPERATOR_HANDOFF_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 32 H1" in sec or "OPERATOR_HANDOFF_MVP.md" in sec

    mapping = json.loads(HANDOFF.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "32",
        "workstream": "H1",
        "passed": True,
        "doc": "docs/OPERATOR_HANDOFF_MVP.md",
        "handoff": "ops/mvp/operator-handoff.json",
        "handoff_complete_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "attestation_claimed": False,
        "live_runs_certified": False,
        "packaging_complete": True,
        "phase_count": len(mapping["phases"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["handoff_complete_claimed"] is False
    assert loaded["go_live_claimed"] is False
    assert loaded["packaging_complete"] is True
