"""Stage 69 A1 — Go-live attestation honesty (not §7 signed Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "golive-attestation.json"
ATTEST = ROOT / "ops" / "launch" / "attestation-matrix.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
PREFLIGHT = ROOT / "ops" / "mvp" / "preflight-verification.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage69_a1_golive_attestation.json"

REQUIRED_IDS = {
    "ga-owner-outline",
    "ga-attestation-pack",
    "ga-mvp-declaration",
    "ga-launch-cert",
    "ga-preflight",
    "ga-production-launch",
    "ga-cutover",
    "ga-plan-honesty",
    "ga-section7-remaining",
    "ga-attestation-remaining",
}
REQUIRED_CATEGORIES = {"attestation", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_golive_attestation_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "69"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["golive_attestation_walk_claimed"] is False
    assert mapping["doc"] == "docs/GOLIVE_ATTESTATION_MVP.md"
    assert "stage69_a1_golive_attestation.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ga-section7-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ga-attestation-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "§7" in d or "section" in d.lower() or "attestation" in d.lower() or "go-live" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage69_plan"],
        mapping["attestation_doc"],
        mapping["attestation_matrix"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["launch_cert_doc"],
        mapping["checklist_map"],
        mapping["preflight_doc"],
        mapping["preflight"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["cutover_doc"],
        mapping["cutover_checklist"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_golive_attestation_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    for key in ("section_7_signed", "attestation_claimed", "sections_1_3_verified"):
        if key in attest:
            assert attest[key] is False
    for key in ("go_live_claimed", "section_7_signed", "attestation_claimed"):
        if key in mvp:
            assert mvp[key] is False
    for key in ("sections_1_3_verified", "section_7_signed", "go_live_claimed"):
        if key in preflight:
            assert preflight[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_69_PLAN.md")
    assert "Go-Live Attestation" in plan or "§7" in plan
    assert "Pre-Flight" in plan or "pre-flight" in plan.lower() or "V1" in plan


def test_golive_attestation_doc_and_readme():
    doc = _read("docs/GOLIVE_ATTESTATION_MVP.md")
    assert "Stage 69 A1" in doc
    assert "test_golive_attestation_a1.py" in doc
    assert "golive-attestation.json" in doc
    assert "section_7_signed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 69 A1" in readme
    assert "GOLIVE_ATTESTATION_MVP.md" in readme
    assert "golive-attestation.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_69_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_golive_attestation_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H69x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_golive_attestation_a1.py" in launch
    assert "Stage 69 A1" in launch
    assert "GOLIVE_ATTESTATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 69 A1" in roadmap
    assert "test_golive_attestation_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 69 A1" in pr
    assert "test_golive_attestation_a1.py" in pr or "GOLIVE_ATTESTATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "69",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/GOLIVE_ATTESTATION_MVP.md",
        "register": "ops/mvp/golive-attestation.json",
        "packaging_complete": True,
        "section_7_signed": False,
        "attestation_claimed": False,
        "go_live_claimed": False,
        "sections_1_3_verified": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["section_7_signed"] is False
    assert loaded["attestation_claimed"] is False
    assert loaded["step_count"] >= 10
