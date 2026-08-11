"""Stage 32 A1 — MVP acceptance archive (not live go-live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "ops" / "mvp" / "acceptance-archive.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage32_a1_acceptance_archive.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_acceptance_archive_honest():
    assert ARCHIVE.is_file()
    mapping = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    assert mapping["stage"] == "32"
    assert mapping["workstream"] == "A1"
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["archive_complete"] is True
    assert mapping["doc"] == "docs/ACCEPTANCE_ARCHIVE_MVP.md"
    assert "stage32_a1_acceptance_archive.json" in mapping["evidence_artifact"]
    entries = mapping["entries"]
    assert mapping["entry_count"] == len(entries) == 31
    assert mapping["stages_covered"] == list(range(1, 32))
    stages = {e["stage"] for e in entries}
    assert stages == set(range(1, 32))
    for entry in entries:
        assert entry["scope_frozen"] is True
        assert entry["go_live_claimed"] is False
        assert (ROOT / entry["exit_criteria"]).is_file(), entry["exit_criteria"]
        assert (ROOT / entry["freeze_file"]).is_file(), entry["freeze_file"]
        assert entry["freeze_adr"].startswith("ADR-")
        assert entry["title"]
    # Spot-check bookends
    first = next(e for e in entries if e["stage"] == 1)
    assert "STAGE_1_EXIT_CRITERIA.md" in first["exit_criteria"]
    assert "ADR-008" in first["freeze_adr"]
    last = next(e for e in entries if e["stage"] == 31)
    assert "STAGE_31_EXIT_CRITERIA.md" in last["exit_criteria"]
    assert "ADR-068" in last["freeze_adr"]
    assert any("go-live" in d.lower() or "§7" in d or "attestation" in d.lower() for d in mapping["deferred"])


def test_acceptance_archive_doc_and_readme():
    doc = _read("docs/ACCEPTANCE_ARCHIVE_MVP.md")
    assert "Stage 32 A1" in doc
    assert "test_acceptance_archive_a1.py" in doc
    assert "acceptance-archive.json" in doc
    assert "stage32_a1_acceptance_archive.json" in doc
    assert "STAGE_31_EXIT_CRITERIA.md" in doc or "Stage 1–31" in doc or "Stage 1-31" in doc
    assert "go_live_claimed" in doc or "go-live" in doc.lower()
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 32 A1" in readme
    assert "ACCEPTANCE_ARCHIVE_MVP.md" in readme
    assert "acceptance-archive.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_32_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_acceptance_archive_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "H1 next" in plan
        or "H1 complete" in plan
        or "N1 next" in plan
        or "B1 next" in plan
        or "D1 next" in plan
        or "H32x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_acceptance_archive_a1.py" in launch
    assert "Stage 32 A1" in launch
    assert "ACCEPTANCE_ARCHIVE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 32 A1" in roadmap
    assert "test_acceptance_archive_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 32 A1" in pr
    assert "test_acceptance_archive_a1.py" in pr or "ACCEPTANCE_ARCHIVE_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 32 A1" in sec or "ACCEPTANCE_ARCHIVE_MVP.md" in sec

    mapping = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "32",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/ACCEPTANCE_ARCHIVE_MVP.md",
        "archive": "ops/mvp/acceptance-archive.json",
        "entry_count": mapping["entry_count"],
        "go_live_claimed": False,
        "section_7_signed": False,
        "attestation_claimed": False,
        "live_runs_certified": False,
        "deferred_implemented_claimed": False,
        "archive_complete": True,
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["go_live_claimed"] is False
    assert loaded["archive_complete"] is True
    assert loaded["entry_count"] == 31
