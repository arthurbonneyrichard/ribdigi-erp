"""Stage 32 N1 — commercial release notes (packaging ≠ production live)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES = ROOT / "ops" / "mvp" / "release-notes.json"
DECLARATION = ROOT / "ops" / "mvp" / "mvp-declaration.json"
ARCHIVE = ROOT / "ops" / "mvp" / "acceptance-archive.json"
HANDOFF = ROOT / "ops" / "mvp" / "operator-handoff.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage32_n1_release_notes.json"

REQUIRED_HIGHLIGHT_IDS = {
    "foundation-commerce",
    "ops-platform",
    "closeout",
    "handoff-archive",
    "remaining-go-live",
    "remaining-deferred-adrs",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_notes_honest():
    assert NOTES.is_file()
    mapping = json.loads(NOTES.read_text(encoding="utf-8"))
    assert mapping["stage"] == "32"
    assert mapping["workstream"] == "N1"
    assert mapping["packaging_complete"] is True
    assert mapping["production_live_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["doc"] == "docs/RELEASE_NOTES_MVP.md"
    assert "Commercial MVP" in mapping["version_label"]
    assert "packaging" in mapping["version_label"].lower()
    assert "stage32_n1_release_notes.json" in mapping["evidence_artifact"]
    highlights = mapping["highlights"]
    assert len(highlights) >= 6
    ids = {h["id"] for h in highlights}
    assert REQUIRED_HIGHLIGHT_IDS.issubset(ids)
    classes = {h["class"] for h in highlights}
    assert "complete_mvp" in classes
    assert "remaining_post_mvp" in classes
    assert "deferred_adr" in classes
    for h in highlights:
        assert h["title"]
        assert h["summary"]
        assert h["class"] in ("complete_mvp", "remaining_post_mvp", "deferred_adr")
    assert any(h["id"] == "remaining-go-live" and h["class"] == "remaining_post_mvp" for h in highlights)
    assert any(h["id"] == "remaining-deferred-adrs" and h["class"] == "deferred_adr" for h in highlights)
    assert any("production live" in d.lower() or "§7" in d or "go-live" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["mvp_declaration"],
        mapping["acceptance_archive"],
        mapping["operator_handoff"],
        mapping["gate_matrix"],
        mapping["operator_remaining_register"],
        mapping["deferred_adr_register"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_release_notes_aligns_declaration_and_handoff():
    mapping = json.loads(NOTES.read_text(encoding="utf-8"))
    declaration = json.loads(DECLARATION.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))

    assert declaration["packaging_complete"] is True
    assert declaration["go_live_claimed"] is False
    assert archive["archive_complete"] is True
    assert archive["go_live_claimed"] is False
    assert handoff["handoff_complete_claimed"] is False
    assert handoff["go_live_claimed"] is False
    assert remaining["live_runs_certified"] is False
    assert mapping["production_live_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["packaging_complete"] is True


def test_release_notes_doc_and_readme():
    doc = _read("docs/RELEASE_NOTES_MVP.md")
    assert "Stage 32 N1" in doc
    assert "test_release_notes_n1.py" in doc
    assert "release-notes.json" in doc
    assert "stage32_n1_release_notes.json" in doc
    assert "MVP_DECLARATION_MVP.md" in doc
    assert "complete_mvp" in doc
    assert "remaining_post_mvp" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 32 N1" in readme
    assert "RELEASE_NOTES_MVP.md" in readme
    assert "release-notes.json" in readme


def test_n1_plan_launch_roadmap():
    plan = _read("docs/STAGE_32_PLAN.md")
    n1_line = [ln for ln in plan.splitlines() if "| **N1** |" in ln][0]
    assert "COMPLETE" in n1_line
    assert "test_release_notes_n1.py" in plan
    assert (
        "N1 next" in plan
        or "N1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "H32x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_release_notes_n1.py" in launch
    assert "Stage 32 N1" in launch
    assert "RELEASE_NOTES_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 32 N1" in roadmap
    assert "test_release_notes_n1.py" in roadmap
    assert "RELEASE_NOTES_MVP.md" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 32 N1" in pr
    assert "test_release_notes_n1.py" in pr or "RELEASE_NOTES_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 32 N1" in sec or "RELEASE_NOTES_MVP.md" in sec

    mapping = json.loads(NOTES.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "32",
        "workstream": "N1",
        "passed": True,
        "doc": "docs/RELEASE_NOTES_MVP.md",
        "notes": "ops/mvp/release-notes.json",
        "packaging_complete": True,
        "production_live_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "highlight_count": len(mapping["highlights"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["production_live_claimed"] is False
    assert loaded["packaging_complete"] is True
