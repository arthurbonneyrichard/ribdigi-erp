"""Operator PITR drill pack packaging (not fake CI PITR success)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "postgres" / "pitr-drill-checklist.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/dr")
EVIDENCE_FILE = EVIDENCE_DIR / "stage28_r1_pitr_drill_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pitr_drill_checklist_exists_and_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "28"
    assert mapping["workstream"] == "R1"
    assert mapping["operator_pitr_drill_executed"] is False
    assert mapping["ci_pitr_success_claimed"] is False
    assert mapping["doc"] == "docs/PITR_DRILL_PACK_MVP.md"
    assert mapping["runbook"] == "docs/DR_WAL_PITR_RUNBOOK.md"
    assert mapping["compose_sketch"] == "ops/backup/docker-compose.wal-drill.example.yml"
    assert len(mapping["steps"]) >= 7
    for step in mapping["steps"]:
        assert step["class"] == "operator_required"
        assert step["title"]
    assert mapping["pass_criteria"]
    deferred = " ".join(mapping["deferred"])
    assert "CI-executed" in deferred or "managed-cloud" in deferred.lower()
    assert "stage28_r1_pitr_drill_pack.json" in mapping["evidence_artifact"]


def test_pitr_drill_pack_mvp_doc():
    doc = _read("docs/PITR_DRILL_PACK_MVP.md")
    assert "Stage 28 R1" in doc
    assert "test_pitr_drill_pack_r1.py" in doc
    assert "pitr-drill-checklist.json" in doc
    assert "DR_WAL_PITR_RUNBOOK.md" in doc
    assert "operator_required" in doc
    assert "stage28_r1_pitr_drill_pack.json" in doc


def test_wal_runbook_extends_with_r1_pack():
    runbook = _read("docs/DR_WAL_PITR_RUNBOOK.md")
    assert "PITR_DRILL_PACK_MVP.md" in runbook
    assert "pitr-drill-checklist.json" in runbook
    assert "Operator PITR drill" in runbook or "operator" in runbook.lower()
    assert "stage28_r1_pitr_drill_pack.json" in runbook
    assert "operator_pitr_drill_executed" in runbook or "packaging" in runbook.lower()


def test_ops_postgres_readme_cites_r1():
    readme = _read("ops/postgres/README.md")
    assert "Stage 28 R1" in readme
    assert "pitr-drill-checklist.json" in readme
    assert "PITR_DRILL_PACK_MVP.md" in readme


def test_pitr_pack_evidence_honest():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "28",
        "workstream": "R1",
        "passed": True,
        "packaging_only": True,
        "operator_pitr_drill_executed": False,
        "ci_pitr_success_claimed": False,
        "checklist": "ops/postgres/pitr-drill-checklist.json",
        "doc": "docs/PITR_DRILL_PACK_MVP.md",
        "runbook": "docs/DR_WAL_PITR_RUNBOOK.md",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["operator_pitr_drill_executed"] is False
    assert loaded["ci_pitr_success_claimed"] is False
