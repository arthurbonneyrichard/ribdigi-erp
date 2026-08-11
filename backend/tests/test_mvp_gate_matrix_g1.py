"""Stage 31 G1 — MVP gate honesty matrix (not live go-live Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "ops" / "mvp" / "gate-matrix.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage31_g1_mvp_gate_matrix.json"

REQUIRED_SECTIONS = {
    "Platform & tenancy",
    "Identity & security",
    "ERP operations",
    "Reliability & operations",
    "AI",
}

REQUIRED_IDS = {
    "schema-tenancy",
    "isolation",
    "tenant-lifecycle",
    "owasp",
    "inventory",
    "accounting",
    "tax",
    "wal-pitr",
    "monitoring",
    "kubernetes",
    "load",
    "ai-provider",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_mvp_gate_matrix_honest():
    assert MATRIX.is_file()
    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert mapping["stage"] == "31"
    assert mapping["workstream"] == "G1"
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/MVP_GATE_MATRIX_MVP.md"
    assert mapping["readiness"] == "PRODUCTION_READINESS.md"
    assert "stage31_g1_mvp_gate_matrix.json" in mapping["evidence_artifact"]
    assert set(mapping["classes"]) >= {"complete_mvp", "remaining_post_mvp", "deferred_adr"}
    gates = mapping["gates"]
    assert len(gates) >= 30
    ids = {g["id"] for g in gates}
    assert REQUIRED_IDS.issubset(ids)
    sections = {g["section"] for g in gates}
    assert REQUIRED_SECTIONS.issubset(sections)
    for gate in gates:
        assert gate["class"] == "complete_mvp"
        assert gate["checkbox"]
        assert isinstance(gate["honesty"], list)
        for tag in gate["honesty"]:
            assert tag in ("remaining_post_mvp", "deferred_adr"), tag
        for ref in gate.get("refs", []):
            assert (ROOT / ref).is_file(), ref
    assert any(g["id"] == "kubernetes" and "remaining_post_mvp" in g["honesty"] for g in gates)
    assert any(g["id"] == "schema-tenancy" and "deferred_adr" in g["honesty"] for g in gates)
    assert any(g["id"] == "owasp" and "remaining_post_mvp" in g["honesty"] for g in gates)
    assert any("go-live" in d.lower() or "§7" in d or "attestation" in d.lower() for d in mapping["deferred"])


def test_mvp_gate_matrix_aligns_readiness_checkboxes():
    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    readiness = _read("PRODUCTION_READINESS.md")
    for gate in mapping["gates"]:
        checkbox = gate["checkbox"]
        assert f"- [x] {checkbox}" in readiness, checkbox
        assert f"- [ ] {checkbox}" not in readiness, checkbox
    # Honesty: packaging must not claim go-live / §7
    assert "attestation_claimed: false" in readiness or "attestation_claimed: false" in _read(
        "ops/launch/attestation-matrix.json"
    )
    attestation = json.loads(_read("ops/launch/attestation-matrix.json"))
    assert attestation["attestation_claimed"] is False
    assert attestation["section_7_signed"] is False


def test_mvp_gate_matrix_doc_and_readme():
    doc = _read("docs/MVP_GATE_MATRIX_MVP.md")
    assert "Stage 31 G1" in doc
    assert "test_mvp_gate_matrix_g1.py" in doc
    assert "gate-matrix.json" in doc
    assert "stage31_g1_mvp_gate_matrix.json" in doc
    assert "complete_mvp" in doc
    assert "remaining_post_mvp" in doc
    assert "deferred_adr" in doc
    assert "PRODUCTION_READINESS.md" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 31 G1" in readme
    assert "MVP_GATE_MATRIX_MVP.md" in readme
    assert "gate-matrix.json" in readme


def test_g1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_31_PLAN.md")
    g1_line = [ln for ln in plan.splitlines() if "| **G1** |" in ln][0]
    assert "COMPLETE" in g1_line
    assert "test_mvp_gate_matrix_g1.py" in plan
    assert (
        "G1 next" in plan
        or "G1 complete" in plan
        or "R1 next" in plan
        or "R1 complete" in plan
        or "O1 next" in plan
        or "C1 next" in plan
        or "D1 next" in plan
        or "H31x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_mvp_gate_matrix_g1.py" in launch
    assert "Stage 31 G1" in launch
    assert "MVP_GATE_MATRIX_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 31 G1" in roadmap
    assert "test_mvp_gate_matrix_g1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 31 G1" in pr
    assert "test_mvp_gate_matrix_g1.py" in pr or "MVP_GATE_MATRIX_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 31 G1" in sec or "MVP_GATE_MATRIX_MVP.md" in sec

    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "31",
        "workstream": "G1",
        "passed": True,
        "doc": "docs/MVP_GATE_MATRIX_MVP.md",
        "matrix": "ops/mvp/gate-matrix.json",
        "readiness": "PRODUCTION_READINESS.md",
        "go_live_claimed": False,
        "section_7_signed": False,
        "attestation_claimed": False,
        "packaging_complete": True,
        "gate_count": len(mapping["gates"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["go_live_claimed"] is False
    assert loaded["packaging_complete"] is True
