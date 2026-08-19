"""Stage 46 L1 — liability / indemnity honesty (not signed liability-cap Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "liability-indemnity.json"
MSA = ROOT / "ops" / "mvp" / "msa-addendum.json"
TOS = ROOT / "ops" / "mvp" / "tos-aup.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage46_l1_liability_indemnity.json"

REQUIRED_IDS = {
    "li-msa-adjacency",
    "li-tos-adjacency",
    "li-dpa-adjacency",
    "li-breach-adjacency",
    "li-vuln-adjacency",
    "li-support-sla",
    "li-residual-risk",
    "li-security-guide",
    "li-cap-remaining",
    "li-indemnity-remaining",
}
REQUIRED_CATEGORIES = {"liability", "indemnity", "contract", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_liability_indemnity_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "46"
    assert mapping["workstream"] == "L1"
    assert mapping["packaging_complete"] is True
    assert mapping["liability_cap_claimed"] is False
    assert mapping["indemnity_signed_claimed"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert mapping["contract_liability_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/LIABILITY_INDEMNITY_MVP.md"
    assert "stage46_l1_liability_indemnity.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "li-cap-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "li-indemnity-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "liability" in d.lower() or "indemnity" in d.lower() or "counsel" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["msa_addendum"],
        mapping["msa_addendum_doc"],
        mapping["tos_aup"],
        mapping["tos_aup_doc"],
        mapping["dpa_subprocessor"],
        mapping["dpa_subprocessor_doc"],
        mapping["breach_notification"],
        mapping["breach_notification_doc"],
        mapping["vuln_disclosure"],
        mapping["vuln_disclosure_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["residual_risk"],
        mapping["residual_risk_doc"],
        mapping["security_guide"],
        mapping["compliance_readiness_doc"],
        mapping["stage46_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_liability_indemnity_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    msa = json.loads(MSA.read_text(encoding="utf-8"))
    tos = json.loads(TOS.read_text(encoding="utf-8"))
    assert mapping["liability_cap_claimed"] is False
    assert mapping["indemnity_signed_claimed"] is False
    assert msa.get("msa_signed_claimed") is False
    assert msa.get("legal_counsel_claimed") is False
    assert tos.get("tos_signed_claimed") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    msa_doc = _read("docs/MSA_ADDENDUM_MVP.md")
    assert "MSA" in msa_doc or "addendum" in msa_doc.lower()
    tos_doc = _read("docs/TOS_AUP_MVP.md")
    assert "ToS" in tos_doc or "AUP" in tos_doc or "Terms" in tos_doc


def test_liability_indemnity_doc_and_readme():
    doc = _read("docs/LIABILITY_INDEMNITY_MVP.md")
    assert "Stage 46 L1" in doc
    assert "test_liability_indemnity_l1.py" in doc
    assert "liability-indemnity.json" in doc
    assert "stage46_l1_liability_indemnity.json" in doc
    assert "liability_cap_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "liability" in doc.lower() or "indemnity" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 46 L1" in readme
    assert "LIABILITY_INDEMNITY_MVP.md" in readme
    assert "liability-indemnity.json" in readme


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_46_PLAN.md")
    l1_line = [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_liability_indemnity_l1.py" in plan
    assert (
        "L1 next" in plan
        or "L1 complete" in plan
        or "W1 next" in plan
        or "W1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H46x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_liability_indemnity_l1.py" in launch
    assert "Stage 46 L1" in launch
    assert "LIABILITY_INDEMNITY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 46 L1" in roadmap
    assert "test_liability_indemnity_l1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 46 L1" in pr
    assert "test_liability_indemnity_l1.py" in pr or "LIABILITY_INDEMNITY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "46",
        "workstream": "L1",
        "passed": True,
        "doc": "docs/LIABILITY_INDEMNITY_MVP.md",
        "register": "ops/mvp/liability-indemnity.json",
        "packaging_complete": True,
        "liability_cap_claimed": False,
        "indemnity_signed_claimed": False,
        "legal_counsel_claimed": False,
        "contract_liability_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["liability_cap_claimed"] is False
    assert loaded["indemnity_signed_claimed"] is False
    assert loaded["step_count"] >= 10
