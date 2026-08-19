"""Stage 31 C1 — commercial MVP declaration (packaging ≠ live go-live / forged §7)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = ROOT / "ops" / "mvp" / "mvp-declaration.json"
EVIDENCE_EXAMPLE = ROOT / "ops" / "mvp" / "mvp-declaration-evidence.example.json"
ATTESTATION = ROOT / "ops" / "launch" / "attestation-matrix.json"
CHECKLIST_MAP = ROOT / "ops" / "launch" / "checklist-map.json"
GATE = ROOT / "ops" / "mvp" / "gate-matrix.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage31_c1_mvp_declaration.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section_body(checklist: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in checklist, heading
    rest = checklist.split(marker, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def test_mvp_declaration_honest():
    assert DECLARATION.is_file()
    mapping = json.loads(DECLARATION.read_text(encoding="utf-8"))
    assert mapping["stage"] == "31"
    assert mapping["workstream"] == "C1"
    assert mapping["packaging_complete"] is True
    assert mapping["commercial_mvp_packaging_declared"] is True
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["doc"] == "docs/MVP_DECLARATION_MVP.md"
    assert mapping["gate_matrix"] == "ops/mvp/gate-matrix.json"
    assert mapping["deferred_adr_register"] == "ops/mvp/deferred-adr-register.json"
    assert mapping["operator_remaining_register"] == "ops/mvp/operator-remaining-register.json"
    assert mapping["attestation_matrix"] == "ops/launch/attestation-matrix.json"
    assert "stage31_c1_mvp_declaration.json" in mapping["evidence_artifact"]
    assert len(mapping["statements"]) >= 4
    assert any(s["id"] == "not-go-live" and s["claimed"] is True for s in mapping["statements"])
    assert any(s["id"] == "packaging" and s["claimed"] is True for s in mapping["statements"])
    assert any("§7" in d or "go-live" in d.lower() or "attestation" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["gate_matrix"],
        mapping["deferred_adr_register"],
        mapping["operator_remaining_register"],
        mapping["attestation_matrix"],
        mapping["checklist_map"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_mvp_declaration_aligns_attestation_and_remaining():
    mapping = json.loads(DECLARATION.read_text(encoding="utf-8"))
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    checklist_map = json.loads(CHECKLIST_MAP.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))

    assert attestation["attestation_claimed"] is False
    assert attestation["section_7_signed"] is False
    assert attestation["sections_1_3_verified"] is False
    assert checklist_map["production_signoff_claimed"] is False
    assert remaining["live_runs_certified"] is False
    assert remaining["attestation_claimed"] is False
    assert gate["go_live_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False


def test_mvp_declaration_evidence_schema_not_forged():
    assert EVIDENCE_EXAMPLE.is_file()
    example = json.loads(EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
    assert example["packaging_complete"] is True
    assert example["commercial_mvp_packaging_declared"] is True
    assert example["passed"] is False
    assert example["go_live_claimed"] is False
    assert example["section_7_signed"] is False
    assert example["attestation_claimed"] is False
    assert "forged" in example["notes"].lower() or "schema example" in example["notes"].lower()
    assert "MVP_DECLARATION_MVP" in example["notes"] or "Stage 31 C1" in example["notes"]


def test_launch_sections_remain_unsigned_with_declaration_doc():
    checklist = _read("docs/LAUNCH_CHECKLIST.md")
    for title in (
        "1. Configuration & secrets",
        "2. Identity & security",
        "3. Integrations (Stage 6–7)",
    ):
        body = _section_body(checklist, title)
        assert re.findall(r"^- \[ \] .+$", body, flags=re.M), title

    signoff = _section_body(checklist, "7. Sign-off")
    assert "| Engineering |" in signoff
    assert re.search(r"\| Engineering \| \| \|", signoff) or "| Engineering | |" in signoff

    doc = _read("docs/MVP_DECLARATION_MVP.md")
    assert "Stage 31 C1" in doc
    assert "test_mvp_declaration_c1.py" in doc
    assert "mvp-declaration.json" in doc
    assert "mvp-declaration-evidence.example.json" in doc
    assert "packaging" in doc.lower()
    assert "not" in doc.lower()
    assert "§7" in doc or "Sign-off" in doc
    assert "stage31_c1_mvp_declaration.json" in doc


def test_c1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_31_PLAN.md")
    c1_line = [ln for ln in plan.splitlines() if "| **C1** |" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_mvp_declaration_c1.py" in plan
    assert (
        "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H31x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_mvp_declaration_c1.py" in launch
    assert "Stage 31 C1" in launch
    assert "MVP_DECLARATION_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 31 C1" in roadmap
    assert "test_mvp_declaration_c1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 31 C1" in pr
    assert "test_mvp_declaration_c1.py" in pr or "MVP_DECLARATION_MVP.md" in pr

    ops = _read("ops/mvp/README.md")
    assert "Stage 31 C1" in ops or "mvp-declaration.json" in ops
    assert "MVP_DECLARATION_MVP.md" in ops

    mapping = json.loads(DECLARATION.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "31",
        "workstream": "C1",
        "passed": True,
        "doc": "docs/MVP_DECLARATION_MVP.md",
        "declaration": "ops/mvp/mvp-declaration.json",
        "evidence_schema": "ops/mvp/mvp-declaration-evidence.example.json",
        "packaging_complete": True,
        "commercial_mvp_packaging_declared": True,
        "go_live_claimed": False,
        "section_7_signed": False,
        "attestation_claimed": False,
        "statements": mapping["statements"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["packaging_complete"] is True
    assert loaded["go_live_claimed"] is False
    assert loaded["section_7_signed"] is False
