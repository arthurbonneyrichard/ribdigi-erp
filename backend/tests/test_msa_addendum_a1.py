"""Stage 39 A1 — MSA security addendum honesty (not signed MSA Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "msa-addendum.json"
ASSURANCE = ROOT / "ops" / "mvp" / "assurance-evidence.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage39_a1_msa_addendum.json"

REQUIRED_IDS = {
    "msa-assurance-evidence",
    "msa-vuln-disclosure",
    "msa-breach-notification",
    "msa-support-sla",
    "msa-dpa-adjacency",
    "msa-security-guide",
    "msa-compliance-themes",
    "msa-attestation-remaining",
    "msa-signed-remaining",
    "msa-exhibit-signed-remaining",
}
REQUIRED_CATEGORIES = {"assurance", "disclosure", "contract", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_msa_addendum_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "39"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["msa_signed_claimed"] is False
    assert mapping["security_exhibit_signed"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert mapping["contract_execution_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/MSA_ADDENDUM_MVP.md"
    assert "stage39_a1_msa_addendum.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "msa-signed-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "msa-assurance-evidence" for s in steps)
    assert any(
        "msa" in d.lower() or "exhibit" in d.lower() or "legal" in d.lower() or "contract" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["assurance_evidence"],
        mapping["assurance_evidence_doc"],
        mapping["vuln_disclosure"],
        mapping["vuln_disclosure_doc"],
        mapping["breach_notification"],
        mapping["breach_notification_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["dpa_subprocessor"],
        mapping["dpa_subprocessor_doc"],
        mapping["security_guide"],
        mapping["compliance_questionnaire_doc"],
        mapping["stage39_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_msa_addendum_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assurance = json.loads(ASSURANCE.read_text(encoding="utf-8"))
    assert mapping["msa_signed_claimed"] is False
    assert mapping["security_exhibit_signed"] is False
    aflags = json.dumps(assurance).lower()
    assert "false" in aflags or "assurance" in aflags or "attestation" in aflags
    for step in mapping["steps"]:
        assert step["done"] is False
    ass_doc = _read("docs/ASSURANCE_EVIDENCE_MVP.md")
    assert "assurance" in ass_doc.lower() or "procurement" in ass_doc.lower()
    dpa = _read("docs/DPA_SUBPROCESSOR_MVP.md")
    assert "DPA" in dpa or "subprocessor" in dpa.lower()


def test_msa_addendum_doc_and_readme():
    doc = _read("docs/MSA_ADDENDUM_MVP.md")
    assert "Stage 39 A1" in doc
    assert "test_msa_addendum_a1.py" in doc
    assert "msa-addendum.json" in doc
    assert "stage39_a1_msa_addendum.json" in doc
    assert "msa_signed_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "MSA" in doc or "addendum" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 39 A1" in readme
    assert "MSA_ADDENDUM_MVP.md" in readme
    assert "msa-addendum.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_39_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_msa_addendum_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H39x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_msa_addendum_a1.py" in launch
    assert "Stage 39 A1" in launch
    assert "MSA_ADDENDUM_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 39 A1" in roadmap
    assert "test_msa_addendum_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 39 A1" in pr
    assert "test_msa_addendum_a1.py" in pr or "MSA_ADDENDUM_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "39",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/MSA_ADDENDUM_MVP.md",
        "register": "ops/mvp/msa-addendum.json",
        "packaging_complete": True,
        "msa_signed_claimed": False,
        "security_exhibit_signed": False,
        "legal_counsel_claimed": False,
        "contract_execution_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["msa_signed_claimed"] is False
    assert loaded["security_exhibit_signed"] is False
    assert loaded["legal_counsel_claimed"] is False
    assert loaded["step_count"] >= 10
