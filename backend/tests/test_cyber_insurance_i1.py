"""Stage 47 I1 — cyber insurance / COI honesty (not issued COI Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "cyber-insurance.json"
LIABILITY = ROOT / "ops" / "mvp" / "liability-indemnity.json"
MSA = ROOT / "ops" / "mvp" / "msa-addendum.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage47_i1_cyber_insurance.json"

REQUIRED_IDS = {
    "ci-liability-adjacency",
    "ci-msa-adjacency",
    "ci-assurance-adjacency",
    "ci-residual-risk",
    "ci-breach-adjacency",
    "ci-remedy-adjacency",
    "ci-compliance-themes",
    "ci-security-guide",
    "ci-coi-remaining",
    "ci-policy-remaining",
}
REQUIRED_CATEGORIES = {"insurance", "coi", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cyber_insurance_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "47"
    assert mapping["workstream"] == "I1"
    assert mapping["packaging_complete"] is True
    assert mapping["insurance_certificate_claimed"] is False
    assert mapping["cyber_insurance_live"] is False
    assert mapping["coi_issued_claimed"] is False
    assert mapping["broker_attestation_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CYBER_INSURANCE_MVP.md"
    assert "stage47_i1_cyber_insurance.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ci-coi-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ci-policy-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "insurance" in d.lower() or "coi" in d.lower() or "cyber" in d.lower() or "broker" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["liability_indemnity"],
        mapping["liability_indemnity_doc"],
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["assurance_evidence"],
        mapping["assurance_evidence_doc"],
        mapping["residual_risk"],
        mapping["residual_risk_doc"],
        mapping["breach_notification"],
        mapping["breach_notification_doc"],
        mapping["service_credit_warranty"],
        mapping["service_credit_warranty_doc"],
        mapping["compliance_questionnaire_doc"],
        mapping["compliance_readiness_doc"],
        mapping["security_guide"],
        mapping["stage47_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_cyber_insurance_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    liability = json.loads(LIABILITY.read_text(encoding="utf-8"))
    msa = json.loads(MSA.read_text(encoding="utf-8"))
    assert mapping["insurance_certificate_claimed"] is False
    assert mapping["cyber_insurance_live"] is False
    assert liability.get("liability_cap_claimed") is False
    assert msa.get("msa_signed_claimed") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    li_doc = _read("docs/LIABILITY_INDEMNITY_MVP.md")
    assert "liability" in li_doc.lower() or "indemnity" in li_doc.lower()
    msa_doc = _read("docs/MSA_ADDENDUM_MVP.md")
    assert "MSA" in msa_doc or "addendum" in msa_doc.lower()


def test_cyber_insurance_doc_and_readme():
    doc = _read("docs/CYBER_INSURANCE_MVP.md")
    assert "Stage 47 I1" in doc
    assert "test_cyber_insurance_i1.py" in doc
    assert "cyber-insurance.json" in doc
    assert "stage47_i1_cyber_insurance.json" in doc
    assert "insurance_certificate_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "insurance" in doc.lower() or "COI" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 47 I1" in readme
    assert "CYBER_INSURANCE_MVP.md" in readme
    assert "cyber-insurance.json" in readme


def test_i1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_47_PLAN.md")
    i1_line = [ln for ln in plan.splitlines() if "| **I1** |" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_cyber_insurance_i1.py" in plan
    assert (
        "I1 next" in plan
        or "I1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H47x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_cyber_insurance_i1.py" in launch
    assert "Stage 47 I1" in launch
    assert "CYBER_INSURANCE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 47 I1" in roadmap
    assert "test_cyber_insurance_i1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 47 I1" in pr
    assert "test_cyber_insurance_i1.py" in pr or "CYBER_INSURANCE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "47",
        "workstream": "I1",
        "passed": True,
        "doc": "docs/CYBER_INSURANCE_MVP.md",
        "register": "ops/mvp/cyber-insurance.json",
        "packaging_complete": True,
        "insurance_certificate_claimed": False,
        "cyber_insurance_live": False,
        "coi_issued_claimed": False,
        "broker_attestation_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["insurance_certificate_claimed"] is False
    assert loaded["cyber_insurance_live"] is False
    assert loaded["step_count"] >= 10
