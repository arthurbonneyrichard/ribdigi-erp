"""Stage 44 R1 — Data residency / localization honesty (not multi-region Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "data-residency.json"
DPA = ROOT / "ops" / "mvp" / "dpa-subprocessor.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage44_r1_data_residency.json"

REQUIRED_IDS = {
    "dr-br-local-laws",
    "dr-adr001-shared-schema",
    "dr-dpa-adjacency",
    "dr-portability-adjacency",
    "dr-erasure-adjacency",
    "dr-cookie-privacy-adjacency",
    "dr-compliance-readiness",
    "dr-compliance-questionnaire",
    "dr-multi-region-remaining",
    "dr-gdpr-residency-remaining",
}
REQUIRED_CATEGORIES = {"residency", "tenancy", "privacy", "compliance", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_data_residency_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "44"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["multi_region_residency_claimed"] is False
    assert mapping["schema_per_tenant_claimed"] is False
    assert mapping["gdpr_residency_cert_claimed"] is False
    assert mapping["customer_region_pinning_live"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/DATA_RESIDENCY_MVP.md"
    assert "stage44_r1_data_residency.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "dr-multi-region-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "dr-gdpr-residency-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "dr-adr001-shared-schema" for s in steps)
    assert any(
        "residency" in d.lower() or "region" in d.lower() or "schema-per-tenant" in d.lower() or "gdpr" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["adr_001_tenancy"],
        mapping["business_requirements"],
        mapping["dpa_subprocessor"],
        mapping["dpa_subprocessor_doc"],
        mapping["data_portability"],
        mapping["data_portability_doc"],
        mapping["erasure_honesty"],
        mapping["erasure_honesty_doc"],
        mapping["cookie_privacy_notice"],
        mapping["cookie_privacy_notice_doc"],
        mapping["compliance_readiness"],
        mapping["compliance_readiness_doc"],
        mapping["compliance_questionnaire"],
        mapping["compliance_questionnaire_doc"],
        mapping["deferred_adr_register"],
        mapping["stage44_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_data_residency_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    dpa = json.loads(DPA.read_text(encoding="utf-8"))
    assert mapping["multi_region_residency_claimed"] is False
    assert mapping["schema_per_tenant_claimed"] is False
    assert dpa.get("dpa_signed_claimed") is False
    adr = _read("docs/ADR_001_TENANCY.md")
    assert "shared-schema" in adr.lower() or "tenant_id" in adr or "schema-per-tenant" in adr.lower()
    for step in mapping["steps"]:
        assert step["done"] is False
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "residency" in br.lower() or "Local Data" in br
    port = _read("docs/DATA_PORTABILITY_MVP.md")
    assert "portability" in port.lower() or "GDPR" in port or "consent" in port.lower()


def test_data_residency_doc_and_readme():
    doc = _read("docs/DATA_RESIDENCY_MVP.md")
    assert "Stage 44 R1" in doc
    assert "test_data_residency_r1.py" in doc
    assert "data-residency.json" in doc
    assert "stage44_r1_data_residency.json" in doc
    assert "multi_region_residency_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Residency" in doc or "Localization" in doc or "residency" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 44 R1" in readme
    assert "DATA_RESIDENCY_MVP.md" in readme
    assert "data-residency.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_44_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_data_residency_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "E1 next" in plan
        or "E1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H44x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_data_residency_r1.py" in launch
    assert "Stage 44 R1" in launch
    assert "DATA_RESIDENCY_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 44 R1" in roadmap
    assert "test_data_residency_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 44 R1" in pr
    assert "test_data_residency_r1.py" in pr or "DATA_RESIDENCY_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "44",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/DATA_RESIDENCY_MVP.md",
        "register": "ops/mvp/data-residency.json",
        "packaging_complete": True,
        "multi_region_residency_claimed": False,
        "schema_per_tenant_claimed": False,
        "gdpr_residency_cert_claimed": False,
        "customer_region_pinning_live": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["multi_region_residency_claimed"] is False
    assert loaded["schema_per_tenant_claimed"] is False
    assert loaded["step_count"] >= 10
