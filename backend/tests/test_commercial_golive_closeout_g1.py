"""Stage 70 G1 — Commercial go-live closeout honesty (not go-live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-golive-closeout.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
ATTEST = ROOT / "ops" / "mvp" / "golive-attestation.json"
FIRST_DAY = ROOT / "ops" / "mvp" / "first-commercial-day.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage70_g1_commercial_golive_closeout.json"

REQUIRED_IDS = {
    "cgc-owner-outline",
    "cgc-mvp-declaration",
    "cgc-attestation",
    "cgc-preflight",
    "cgc-first-day",
    "cgc-production-launch",
    "cgc-continuity",
    "cgc-plan-honesty",
    "cgc-golive-remaining",
    "cgc-section7-remaining",
}
REQUIRED_CATEGORIES = {"closeout", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_commercial_golive_closeout_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "70"
    assert mapping["workstream"] == "G1"
    assert mapping["packaging_complete"] is True
    assert mapping["go_live_claimed"] is False
    assert mapping["commercial_golive_closeout_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["first_commercial_day_claimed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["doc"] == "docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md"
    assert "stage70_g1_commercial_golive_closeout.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "cgc-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "cgc-section7-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "go-live" in d.lower() or "closeout" in d.lower() or "section" in d.lower() or "first" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage70_plan"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["golive_attestation_doc"],
        mapping["golive_attestation"],
        mapping["preflight_doc"],
        mapping["preflight"],
        mapping["first_commercial_day_doc"],
        mapping["first_commercial_day"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["continuity_doc"],
        mapping["continuity"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_commercial_golive_closeout_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    first_day = json.loads(FIRST_DAY.read_text(encoding="utf-8"))
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    for key in ("go_live_claimed", "section_7_signed", "attestation_claimed"):
        if key in mvp:
            assert mvp[key] is False
    for key in ("section_7_signed", "attestation_claimed", "go_live_claimed"):
        if key in attest:
            assert attest[key] is False
    for key in ("first_commercial_day_claimed", "go_live_claimed", "section_7_signed"):
        if key in first_day:
            assert first_day[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_70_PLAN.md")
    assert "Closeout" in plan or "Go-Live" in plan
    assert "First Commercial Day" in plan


def test_commercial_golive_closeout_doc_and_readme():
    doc = _read("docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md")
    assert "Stage 70 G1" in doc
    assert "test_commercial_golive_closeout_g1.py" in doc
    assert "commercial-golive-closeout.json" in doc
    assert "go_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 70 G1" in readme
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in readme
    assert "commercial-golive-closeout.json" in readme


def test_g1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_70_PLAN.md")
    g1_line = [ln for ln in plan.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_commercial_golive_closeout_g1.py" in plan
    assert (
        "G1 next" in plan
        or "G1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H70x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_commercial_golive_closeout_g1.py" in launch
    assert "Stage 70 G1" in launch
    assert "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 70 G1" in roadmap
    assert "test_commercial_golive_closeout_g1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 70 G1" in pr
    assert "test_commercial_golive_closeout_g1.py" in pr or "COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "70",
        "workstream": "G1",
        "passed": True,
        "doc": "docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md",
        "register": "ops/mvp/commercial-golive-closeout.json",
        "packaging_complete": True,
        "go_live_claimed": False,
        "commercial_golive_closeout_claimed": False,
        "section_7_signed": False,
        "first_commercial_day_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["go_live_claimed"] is False
    assert loaded["step_count"] >= 10
