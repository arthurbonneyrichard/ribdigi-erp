"""Stage 66 L1 — Production launch honesty (not live go-live / §7 signed Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "production-launch.json"
ATTEST = ROOT / "ops" / "launch" / "attestation-matrix.json"
MVP = ROOT / "ops" / "mvp" / "mvp-declaration.json"
GATE = ROOT / "ops" / "mvp" / "gate-matrix.json"
CUTOVER = ROOT / "ops" / "launch" / "cutover-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage66_l1_production_launch.json"

REQUIRED_IDS = {
    "pl-owner-outline",
    "pl-cutover",
    "pl-attestation",
    "pl-mvp-declaration",
    "pl-prod-gha",
    "pl-release-pipeline",
    "pl-first-tenant-adj",
    "pl-plan-honesty",
    "pl-cutover-remaining",
    "pl-section7-remaining",
    "pl-launch-remaining",
}
REQUIRED_CATEGORIES = {"launch", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_production_launch_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "66"
    assert mapping["workstream"] == "L1"
    assert mapping["packaging_complete"] is True
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["production_cutover_claimed"] is False
    assert mapping["production_launch_live_claimed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["mvp_production_launch_complete_claimed"] is False
    assert mapping["doc"] == "docs/PRODUCTION_LAUNCH_MVP.md"
    assert "stage66_l1_production_launch.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "pl-cutover-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pl-section7-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pl-launch-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "cutover" in d.lower() or "§7" in d or "section" in d.lower() or "go-live" in d.lower() or "launch" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage66_plan"],
        mapping["cutover_doc"],
        mapping["cutover_checklist"],
        mapping["attestation_doc"],
        mapping["attestation_matrix"],
        mapping["mvp_declaration_doc"],
        mapping["mvp_declaration"],
        mapping["mvp_gate_doc"],
        mapping["mvp_gate"],
        mapping["launch_cert_doc"],
        mapping["prod_gha_template"],
        mapping["release_pipeline_doc"],
        mapping["release_pipeline"],
        mapping["first_tenant_doc"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_production_launch_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    mvp = json.loads(MVP.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["production_cutover_claimed"] is False
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
    plan = _read("docs/STAGE_66_PLAN.md")
    assert "Production Cutover" in plan or "Go-Live Attestation" in plan
    assert "MVP Production Launch" in plan


def test_production_launch_doc_and_readme():
    doc = _read("docs/PRODUCTION_LAUNCH_MVP.md")
    assert "Stage 66 L1" in doc
    assert "test_production_launch_l1.py" in doc
    assert "production-launch.json" in doc
    assert "stage66_l1_production_launch.json" in doc
    assert "go_live_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "cutover" in doc.lower() or "§7" in doc or "launch" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 66 L1" in readme
    assert "PRODUCTION_LAUNCH_MVP.md" in readme
    assert "production-launch.json" in readme


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_66_PLAN.md")
    l1_line = [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_production_launch_l1.py" in plan
    assert (
        "L1 next" in plan
        or "L1 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H66x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_production_launch_l1.py" in launch
    assert "Stage 66 L1" in launch
    assert "PRODUCTION_LAUNCH_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 66 L1" in roadmap
    assert "test_production_launch_l1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 66 L1" in pr
    assert "test_production_launch_l1.py" in pr or "PRODUCTION_LAUNCH_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "66",
        "workstream": "L1",
        "passed": True,
        "doc": "docs/PRODUCTION_LAUNCH_MVP.md",
        "register": "ops/mvp/production-launch.json",
        "packaging_complete": True,
        "go_live_claimed": False,
        "section_7_signed": False,
        "production_cutover_claimed": False,
        "production_launch_live_claimed": False,
        "attestation_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["go_live_claimed"] is False
    assert loaded["section_7_signed"] is False
    assert loaded["production_cutover_claimed"] is False
    assert loaded["step_count"] >= 10
