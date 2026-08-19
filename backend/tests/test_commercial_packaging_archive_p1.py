"""Stage 72 P1 — Commercial packaging archive honesty (not archive live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-packaging-archive.json"
ARCHIVE = ROOT / "ops" / "mvp" / "acceptance-archive.json"
RESIDUAL = ROOT / "ops" / "mvp" / "commercial-residual.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage72_p1_commercial_packaging_archive.json"

REQUIRED_IDS = {
    "cpa-owner-outline",
    "cpa-acceptance-archive",
    "cpa-backlog",
    "cpa-release-notes",
    "cpa-mvp-declaration",
    "cpa-residual",
    "cpa-acceptance",
    "cpa-plan-honesty",
    "cpa-archive-remaining",
    "cpa-golive-remaining",
}
REQUIRED_CATEGORIES = {"archive", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_packaging_archive_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "72"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    for k in (
        "packaging_archive_live_claimed",
        "residual_closed_claimed",
        "commercial_acceptance_claimed",
        "go_live_claimed",
        "section_7_signed",
        "attestation_claimed",
    ):
        assert mapping[k] is False
    assert mapping["doc"] == "docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md"
    assert "stage72_p1_commercial_packaging_archive.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "cpa-archive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cpa-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "archive" in d.lower() or "residual" in d.lower() or "go-live" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage72_plan"],
        mapping["acceptance_archive_doc"],
        mapping["acceptance_archive"],
        mapping["backlog_doc"],
        mapping["backlog"],
        mapping["release_notes_doc"],
        mapping["release_notes"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["residual_doc"],
        mapping["residual"],
        mapping["acceptance_doc"],
        mapping["acceptance"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_commercial_packaging_archive_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    assert mapping["packaging_archive_live_claimed"] is False
    for key in ("go_live_claimed", "section_7_signed"):
        if key in archive:
            assert archive[key] is False
    for key in ("residual_closed_claimed", "go_live_claimed"):
        if key in residual:
            assert residual[key] is False
    for key in ("go_live_claimed", "section_7_signed", "attestation_claimed"):
        if key in mvp:
            assert mvp[key] is False
    plan = _read("docs/STAGE_72_PLAN.md")
    assert "Archive" in plan or "Packaging" in plan
    assert "Residual" in plan


def test_commercial_packaging_archive_doc_and_readme():
    doc = _read("docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md")
    assert "Stage 72 P1" in doc
    assert "test_commercial_packaging_archive_p1.py" in doc
    assert "commercial-packaging-archive.json" in doc
    assert "not" in doc.lower()
    readme = _read("ops/mvp/README.md")
    assert "Stage 72 P1" in readme
    assert "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in readme
    assert "commercial-packaging-archive.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_72_PLAN.md")
    assert "COMPLETE" in [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "test_commercial_packaging_archive_p1.py" in plan
    assert any(
        x in plan
        for x in (
            "P1 next",
            "P1 complete",
            "D1 next",
            "D1 complete",
            "H72x next",
            "Closed",
            "exit met",
        )
    )
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_packaging_archive_p1.py" in launch
    assert "Stage 72 P1" in launch
    assert "COMMERCIAL_PACKAGING_ARCHIVE_MVP.md" in launch
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 72 P1" in roadmap
    assert "test_commercial_packaging_archive_p1.py" in roadmap
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 72 P1" in pr
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "72",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md",
        "register": "ops/mvp/commercial-packaging-archive.json",
        "packaging_complete": True,
        "packaging_archive_live_claimed": False,
        "residual_closed_claimed": False,
        "go_live_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["packaging_archive_live_claimed"] is False
    assert loaded["step_count"] >= 10
