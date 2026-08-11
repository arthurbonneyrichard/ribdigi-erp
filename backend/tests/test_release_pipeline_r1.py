"""Stage 65 R1 — Release pipeline honesty (not signed MVP RC Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "release-pipeline.json"
ATTEST = ROOT / "ops" / "launch" / "attestation-matrix.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
GATE = ROOT / "ops" / "mvp" / "gate-matrix.json"
CUTOVER = ROOT / "ops" / "launch" / "cutover-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage65_r1_release_pipeline.json"

REQUIRED_IDS = {
    "rp-owner-outline",
    "rp-staging-gha",
    "rp-security-scan",
    "rp-pentest",
    "rp-attestation",
    "rp-mvp-declaration",
    "rp-cutover",
    "rp-release-notes",
    "rp-plan-honesty",
    "rp-rc-remaining",
    "rp-staging-remaining",
}
REQUIRED_CATEGORIES = {"pipeline", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_pipeline_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "65"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["mvp_release_candidate_signed"] is False
    assert mapping["release_pipeline_live_claimed"] is False
    assert mapping["staging_promotion_live_claimed"] is False
    assert mapping["security_review_signed_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/RELEASE_PIPELINE_MVP.md"
    assert "stage65_r1_release_pipeline.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "rp-rc-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "rp-staging-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "release" in d.lower() or "candidate" in d.lower() or "staging" in d.lower() or "rc" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage65_plan"],
        mapping["staging_gha_doc"],
        mapping["staging_gha_template"],
        mapping["security_scan_doc"],
        mapping["pentest_doc"],
        mapping["pentest_checklist"],
        mapping["attestation_doc"],
        mapping["attestation_matrix"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["mvp_gate_doc"],
        mapping["mvp_gate"],
        mapping["cutover_doc"],
        mapping["cutover_checklist"],
        mapping["release_notes_doc"],
        mapping["release_notes"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_release_pipeline_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    assert mapping["mvp_release_candidate_signed"] is False
    assert mapping["staging_promotion_live_claimed"] is False
    for key in ("attestation_claimed", "section_7_signed"):
        if key in attest:
            assert attest[key] is False
    for key in ("go_live_claimed", "section_7_signed", "attestation_claimed"):
        if key in mvp:
            assert mvp[key] is False
        if key in gate:
            assert gate[key] is False
    for key in ("production_cutover_claimed", "section_7_signed"):
        if key in cutover:
            assert cutover[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_65_PLAN.md")
    assert "MVP Release Candidate" in plan or "Release Candidate" in plan
    assert "Internal QA" in plan or "Staging" in plan


def test_release_pipeline_doc_and_readme():
    doc = _read("docs/RELEASE_PIPELINE_MVP.md")
    assert "Stage 65 R1" in doc
    assert "test_release_pipeline_r1.py" in doc
    assert "release-pipeline.json" in doc
    assert "stage65_r1_release_pipeline.json" in doc
    assert "mvp_release_candidate_signed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "release" in doc.lower() or "candidate" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 65 R1" in readme
    assert "RELEASE_PIPELINE_MVP.md" in readme
    assert "release-pipeline.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_65_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_release_pipeline_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "P1 next" in plan
        or "P1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H65x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_release_pipeline_r1.py" in launch
    assert "Stage 65 R1" in launch
    assert "RELEASE_PIPELINE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 65 R1" in roadmap
    assert "test_release_pipeline_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 65 R1" in pr
    assert "test_release_pipeline_r1.py" in pr or "RELEASE_PIPELINE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "65",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/RELEASE_PIPELINE_MVP.md",
        "register": "ops/mvp/release-pipeline.json",
        "packaging_complete": True,
        "mvp_release_candidate_signed": False,
        "release_pipeline_live_claimed": False,
        "staging_promotion_live_claimed": False,
        "security_review_signed_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["mvp_release_candidate_signed"] is False
    assert loaded["staging_promotion_live_claimed"] is False
    assert loaded["step_count"] >= 10
