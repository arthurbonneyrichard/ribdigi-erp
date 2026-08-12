"""Stage 28 C1 — operator ~1000-VU cert pack (not forged VU certificate)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "loadtest" / "1000vu-cert-checklist.json"
RUN_EXAMPLE = ROOT / "ops" / "loadtest" / "operator_1000vu_run.example.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/loadtest")
EVIDENCE_FILE = EVIDENCE_DIR / "stage28_c1_load_cert_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_1000vu_checklist_exists_and_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "28"
    assert mapping["workstream"] == "C1"
    assert mapping["operator_1000vu_executed"] is False
    assert mapping["ci_1000vu_certificate_claimed"] is False
    assert mapping["doc"] == "docs/LOAD_CERT_PACK_MVP.md"
    assert mapping["capacity_mvp"] == "docs/LOAD_CAPACITY_MVP.md"
    assert mapping["targets"]["concurrent_users"] == 1000
    assert mapping["targets"]["p95_ms"] == 500
    assert mapping["targets"]["max_error_rate"] == 0.0
    assert len(mapping["steps"]) >= 5
    for step in mapping["steps"]:
        assert step["class"] == "operator_required"
    schema = mapping["artifact_schema"]
    for field in (
        "run_id",
        "concurrent_users",
        "p95_ms",
        "error_rate",
        "passed",
        "operator",
    ):
        assert field in schema["required_fields"], field
    assert "stage28_c1_load_cert_pack.json" in mapping["evidence_artifact"]
    assert any("1000" in d or "CI" in d for d in mapping["deferred"])


def test_operator_run_schema_example_not_forged_pass():
    assert RUN_EXAMPLE.is_file()
    example = json.loads(RUN_EXAMPLE.read_text(encoding="utf-8"))
    assert example["passed"] is False
    assert example["concurrent_users"] == 1000
    for field in (
        "run_id",
        "started_at",
        "finished_at",
        "base_url",
        "tool",
        "p50_ms",
        "p95_ms",
        "error_rate",
        "operator",
        "notes",
    ):
        assert field in example, field
    assert "forged" in example["notes"].lower() or "schema example" in example["notes"].lower()
    assert "LOAD_CERT_PACK_MVP" in example["notes"] or "Stage 28 C1" in example["notes"]


def test_load_cert_pack_mvp_doc():
    doc = _read("docs/LOAD_CERT_PACK_MVP.md")
    assert "Stage 28 C1" in doc
    assert "test_load_cert_pack_c1.py" in doc
    assert "1000vu-cert-checklist.json" in doc
    assert "operator_1000vu_run.example.json" in doc
    assert "LOAD_CAPACITY_MVP.md" in doc
    assert "1000" in doc
    assert "500" in doc
    assert "not" in doc.lower()
    assert "stage28_c1_load_cert_pack.json" in doc


def test_load_capacity_extended_for_c1():
    cap = _read("docs/LOAD_CAPACITY_MVP.md")
    assert "Stage 28 C1" in cap or "LOAD_CERT_PACK_MVP.md" in cap
    assert "1000vu-cert-checklist.json" in cap or "LOAD_CERT_PACK_MVP" in cap
    assert "Remaining" in cap or "deferred" in cap.lower() or "not" in cap.lower()

    readme = _read("ops/loadtest/README.md")
    assert "Stage 28 C1" in readme
    assert "LOAD_CERT_PACK_MVP.md" in readme
    assert "1000vu-cert-checklist.json" in readme

    # Harness still present
    assert (ROOT / "backend" / "loadtest" / "run_baseline.py").is_file()
    assert (ROOT / "backend" / "loadtest" / "locustfile.py").is_file()


def test_load_cert_pack_evidence_and_readiness():
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 28 C1" in pr
    assert "test_load_cert_pack_c1.py" in pr or "LOAD_CERT_PACK_MVP.md" in pr
    load_gate = pr.split("- [x] Load/performance tests meet documented targets.")[1].split(
        "- ["
    )[0]
    assert "Stage 28 C1" in load_gate or "LOAD_CERT_PACK_MVP" in load_gate
    assert "Remaining" in load_gate or "1000" in load_gate
    assert "operator" in load_gate.lower() or "staging" in load_gate.lower()

    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "28",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/LOAD_CERT_PACK_MVP.md",
        "checklist": "ops/loadtest/1000vu-cert-checklist.json",
        "run_schema_example": "ops/loadtest/operator_1000vu_run.example.json",
        "capacity_mvp": "docs/LOAD_CAPACITY_MVP.md",
        "operator_1000vu_executed": False,
        "ci_1000vu_certificate_claimed": False,
        "packaging_complete": True,
        "targets": mapping["targets"],
        "steps": mapping["steps"],
        "pass_criteria": mapping["pass_criteria"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["operator_1000vu_executed"] is False
    assert loaded["ci_1000vu_certificate_claimed"] is False
    assert loaded["packaging_complete"] is True
