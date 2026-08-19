"""Stage 39 P1 — DPA / subprocessor honesty (not signed DPA Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "dpa-subprocessor.json"
QUESTIONNAIRE = ROOT / "ops" / "mvp" / "compliance-questionnaire.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage39_p1_dpa_subprocessor.json"

REQUIRED_IDS = {
    "dpa-compliance-questionnaire",
    "dpa-compliance-readiness",
    "dpa-object-storage",
    "dpa-smtp-email",
    "dpa-redis-celery",
    "dpa-optional-providers",
    "dpa-portability-erasure",
    "dpa-tenancy-honesty",
    "dpa-signed-remaining",
    "dpa-register-live-remaining",
}
REQUIRED_CATEGORIES = {"compliance", "subprocessor", "deferred", "data-protection", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_dpa_subprocessor_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "39"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["dpa_signed_claimed"] is False
    assert mapping["subprocessor_register_live"] is False
    assert mapping["legal_counsel_claimed"] is False
    assert mapping["contract_execution_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DPA_SUBPROCESSOR_MVP.md"
    assert "stage39_p1_dpa_subprocessor.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "dpa-signed-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "dpa-object-storage" for s in steps)
    assert any(
        "dpa" in d.lower() or "subprocessor" in d.lower() or "legal" in d.lower() or "contract" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["compliance_questionnaire"],
        mapping["compliance_questionnaire_doc"],
        mapping["compliance_readiness"],
        mapping["compliance_readiness_doc"],
        mapping["data_portability"],
        mapping["data_portability_doc"],
        mapping["erasure_honesty"],
        mapping["erasure_honesty_doc"],
        mapping["adr_001"],
        mapping["stage39_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_dpa_subprocessor_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    questionnaire = json.loads(QUESTIONNAIRE.read_text(encoding="utf-8"))
    assert mapping["dpa_signed_claimed"] is False
    assert mapping["subprocessor_register_live"] is False
    qflags = json.dumps(questionnaire).lower()
    assert "gdpr" in qflags or "privacy" in qflags or "data protection" in qflags
    for step in mapping["steps"]:
        assert step["done"] is False
    adr = _read("docs/ADR_001_TENANCY.md")
    assert "tenant" in adr.lower() or "schema" in adr.lower()
    port = _read("docs/DATA_PORTABILITY_MVP.md")
    assert "portability" in port.lower() or "GDPR" in port


def test_dpa_subprocessor_doc_and_readme():
    doc = _read("docs/DPA_SUBPROCESSOR_MVP.md")
    assert "Stage 39 P1" in doc
    assert "test_dpa_subprocessor_p1.py" in doc
    assert "dpa-subprocessor.json" in doc
    assert "stage39_p1_dpa_subprocessor.json" in doc
    assert "dpa_signed_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "subprocessor" in doc.lower() or "DPA" in doc

    readme = _read("ops/mvp/README.md")
    assert "Stage 39 P1" in readme
    assert "DPA_SUBPROCESSOR_MVP.md" in readme
    assert "dpa-subprocessor.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_39_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_dpa_subprocessor_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H39x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_dpa_subprocessor_p1.py" in launch
    assert "Stage 39 P1" in launch
    assert "DPA_SUBPROCESSOR_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 39 P1" in roadmap
    assert "test_dpa_subprocessor_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 39 P1" in pr
    assert "test_dpa_subprocessor_p1.py" in pr or "DPA_SUBPROCESSOR_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "39",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/DPA_SUBPROCESSOR_MVP.md",
        "register": "ops/mvp/dpa-subprocessor.json",
        "packaging_complete": True,
        "dpa_signed_claimed": False,
        "subprocessor_register_live": False,
        "legal_counsel_claimed": False,
        "contract_execution_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["dpa_signed_claimed"] is False
    assert loaded["subprocessor_register_live"] is False
    assert loaded["legal_counsel_claimed"] is False
    assert loaded["step_count"] >= 10
