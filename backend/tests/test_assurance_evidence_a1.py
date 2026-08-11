"""Stage 34 A1 — assurance evidence (not live attestation / §7 Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "assurance-evidence.json"
ATTESTATION = ROOT / "ops" / "launch" / "attestation-matrix.json"
RESIDUAL = ROOT / "ops" / "mvp" / "residual-risk-register.json"
COMPLIANCE = ROOT / "ops" / "mvp" / "compliance-readiness-register.json"
LEDGER = ROOT / "ops" / "evidence" / "ledger.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage34_a1_assurance_evidence.json"

REQUIRED_IDS = {
    "ae-security-scan",
    "ae-pentest-readiness",
    "ae-launch-cert",
    "ae-attestation-readiness",
    "ae-evidence-ledger",
    "ae-residual-risk",
    "ae-compliance-readiness",
    "ae-cutover-remaining",
    "ae-security-guide",
    "ae-tenancy-isolation",
}
REQUIRED_CATEGORIES = {
    "security",
    "launch",
    "attestation",
    "evidence",
    "risk",
    "compliance",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_assurance_evidence_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "34"
    assert mapping["workstream"] == "A1"
    assert mapping["packaging_complete"] is True
    assert mapping["customer_assurance_claimed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["vendor_pen_test_purchased"] is False
    assert mapping["certification_complete_claimed"] is False
    assert mapping["doc"] == "docs/ASSURANCE_EVIDENCE_MVP.md"
    assert "stage34_a1_assurance_evidence.json" in mapping["evidence_artifact"]
    items = mapping["items"]
    assert len(items) >= 10
    ids = {i["id"] for i in items}
    assert REQUIRED_IDS.issubset(ids)
    cats = {i["category"] for i in items}
    assert REQUIRED_CATEGORIES.issubset(cats)
    for item in items:
        assert item["done"] is False
        assert item["status"] in ("indexed",)
        assert item["title"]
        assert item["source"]
        assert isinstance(item["pack_refs"], list) and item["pack_refs"]
        for pack in item["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(i["id"] == "ae-attestation-readiness" for i in items)
    assert any("attestation" in d.lower() or "§7" in d for d in mapping["deferred"])
    for rel in (
        mapping["attestation_matrix"],
        mapping["residual_risk_register"],
        mapping["compliance_readiness_register"],
        mapping["evidence_ledger"],
        mapping["launch_cert"],
        mapping["pentest_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_assurance_evidence_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    compliance = json.loads(COMPLIANCE.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))

    assert attestation["attestation_claimed"] is False
    assert attestation["section_7_signed"] is False
    assert residual["risks_closed_claimed"] is False
    assert residual["go_live_claimed"] is False
    assert compliance["soc2_complete_claimed"] is False
    assert compliance["iso27001_complete_claimed"] is False
    assert ledger.get("attestation_claimed") is False
    assert ledger.get("section_7_signed") is False
    assert mapping["customer_assurance_claimed"] is False
    assert mapping["attestation_claimed"] is False
    for item in mapping["items"]:
        assert item["done"] is False


def test_assurance_evidence_doc_and_readme():
    doc = _read("docs/ASSURANCE_EVIDENCE_MVP.md")
    assert "Stage 34 A1" in doc
    assert "test_assurance_evidence_a1.py" in doc
    assert "assurance-evidence.json" in doc
    assert "stage34_a1_assurance_evidence.json" in doc
    assert "ATTESTATION_PACK_MVP.md" in doc
    assert "RESIDUAL_RISK_MVP.md" in doc
    assert "customer_assurance_claimed" in doc or "attestation_claimed" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 34 A1" in readme
    assert "ASSURANCE_EVIDENCE_MVP.md" in readme
    assert "assurance-evidence.json" in readme


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_34_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_assurance_evidence_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H34x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_assurance_evidence_a1.py" in launch
    assert "Stage 34 A1" in launch
    assert "ASSURANCE_EVIDENCE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 34 A1" in roadmap
    assert "test_assurance_evidence_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 34 A1" in pr
    assert "test_assurance_evidence_a1.py" in pr or "ASSURANCE_EVIDENCE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "34",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/ASSURANCE_EVIDENCE_MVP.md",
        "register": "ops/mvp/assurance-evidence.json",
        "packaging_complete": True,
        "customer_assurance_claimed": False,
        "attestation_claimed": False,
        "section_7_signed": False,
        "go_live_claimed": False,
        "item_count": len(mapping["items"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["customer_assurance_claimed"] is False
    assert loaded["attestation_claimed"] is False
    assert loaded["item_count"] >= 10
