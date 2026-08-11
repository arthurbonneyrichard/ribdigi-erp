"""Stage 69 V1 — Pre-flight verification honesty (not §§1–3 verified Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "preflight-verification.json"
ATTEST = ROOT / "ops" / "launch" / "attestation-matrix.json"
CUTOVER = ROOT / "ops" / "launch" / "cutover-checklist.json"
LAUNCH = ROOT / "ops" / "mvp" / "production-launch.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage69_v1_preflight_verification.json"

REQUIRED_IDS = {
    "pf-owner-outline",
    "pf-launch-cert",
    "pf-cutover",
    "pf-attestation-map",
    "pf-production-launch",
    "pf-dual-console",
    "pf-plan-honesty",
    "pf-sections-remaining",
    "pf-golive-remaining",
    "pf-preflight-remaining",
}
REQUIRED_CATEGORIES = {"preflight", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_preflight_verification_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "69"
    assert mapping["workstream"] == "V1"
    assert mapping["packaging_complete"] is True
    assert mapping["sections_1_3_verified"] is False
    assert mapping["preflight_verified_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/PREFLIGHT_VERIFICATION_MVP.md"
    assert "stage69_v1_preflight_verification.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "pf-sections-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pf-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "pf-preflight-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "1" in d or "3" in d or "§" in d or "section" in d.lower() or "pre-flight" in d.lower() or "preflight" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage69_plan"],
        mapping["launch_cert_doc"],
        mapping["checklist_map"],
        mapping["cutover_doc"],
        mapping["cutover_checklist"],
        mapping["attestation_doc"],
        mapping["attestation_matrix"],
        mapping["production_launch_doc"],
        mapping["production_launch"],
        mapping["house_console_doc"],
        mapping["tenant_console_doc"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_preflight_verification_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    attest = json.loads(ATTEST.read_text(encoding="utf-8"))
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    launch = json.loads(LAUNCH.read_text(encoding="utf-8"))
    assert mapping["sections_1_3_verified"] is False
    assert mapping["section_7_signed"] is False
    for key in ("sections_1_3_verified", "section_7_signed", "attestation_claimed"):
        if key in attest:
            assert attest[key] is False
    for key in ("production_cutover_claimed", "section_7_signed"):
        if key in cutover:
            assert cutover[key] is False
    for key in ("go_live_claimed", "section_7_signed", "production_cutover_claimed"):
        if key in launch:
            assert launch[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    plan = _read("docs/STAGE_69_PLAN.md")
    assert "Pre-Flight" in plan or "pre-flight" in plan.lower() or "§§1" in plan or "1–3" in plan
    assert "Go-Live Attestation" in plan or "§7" in plan


def test_preflight_verification_doc_and_readme():
    doc = _read("docs/PREFLIGHT_VERIFICATION_MVP.md")
    assert "Stage 69 V1" in doc
    assert "test_preflight_verification_v1.py" in doc
    assert "preflight-verification.json" in doc
    assert "sections_1_3_verified" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 69 V1" in readme
    assert "PREFLIGHT_VERIFICATION_MVP.md" in readme
    assert "preflight-verification.json" in readme


def test_v1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_69_PLAN.md")
    v1_line = [ln for ln in plan.splitlines() if "| **V1** |" in ln][0]
    assert "COMPLETE" in v1_line
    assert "test_preflight_verification_v1.py" in plan
    assert (
        "V1 next" in plan
        or "V1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H69x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_preflight_verification_v1.py" in launch
    assert "Stage 69 V1" in launch
    assert "PREFLIGHT_VERIFICATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 69 V1" in roadmap
    assert "test_preflight_verification_v1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 69 V1" in pr
    assert "test_preflight_verification_v1.py" in pr or "PREFLIGHT_VERIFICATION_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "69",
        "workstream": "V1",
        "passed": True,
        "doc": "docs/PREFLIGHT_VERIFICATION_MVP.md",
        "register": "ops/mvp/preflight-verification.json",
        "packaging_complete": True,
        "sections_1_3_verified": False,
        "preflight_verified_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["sections_1_3_verified"] is False
    assert loaded["step_count"] >= 10
