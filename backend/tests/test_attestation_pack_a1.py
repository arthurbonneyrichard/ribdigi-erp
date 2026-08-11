"""Stage 30 A1 — go-live attestation matrix (not forged §7 / attestation Complete)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "ops" / "launch" / "attestation-matrix.json"
EVIDENCE_EXAMPLE = ROOT / "ops" / "launch" / "attestation-evidence.example.json"
LEDGER = ROOT / "ops" / "evidence" / "ledger.json"
CHECKLIST_MAP = ROOT / "ops" / "launch" / "checklist-map.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage30_a1_attestation_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section_body(checklist: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in checklist, heading
    rest = checklist.split(marker, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def test_attestation_matrix_honest():
    assert MATRIX.is_file()
    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert mapping["stage"] == "30"
    assert mapping["workstream"] == "A1"
    assert mapping["attestation_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["doc"] == "docs/ATTESTATION_PACK_MVP.md"
    assert mapping["evidence_ledger"] == "ops/evidence/ledger.json"
    assert mapping["launch_cert_mvp"] == "docs/LAUNCH_CERT_MVP.md"
    assert mapping["cutover_pack_mvp"] == "docs/CUTOVER_PACK_MVP.md"
    assert mapping["checklist"] == "docs/LAUNCH_CHECKLIST.md"
    assert mapping["launch_sections"] == ["1", "2", "3", "7"]
    assert len(mapping["required_honesty_flags"]) >= 8
    assert "section_7_signed" in mapping["required_honesty_flags"]
    assert len(mapping["gates"]) >= 4
    for gate in mapping["gates"]:
        assert gate["class"] == "operator_required"
    assert any(g.get("maps_to") == ["7"] or "7" in g.get("maps_to", []) for g in mapping["gates"])
    assert "stage30_a1_attestation_pack.json" in mapping["evidence_artifact"]
    assert any("§7" in d or "attestation" in d.lower() or "live" in d.lower() for d in mapping["deferred"])


def test_attestation_aligns_ledger_and_launch():
    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    checklist_map = json.loads(CHECKLIST_MAP.read_text(encoding="utf-8"))

    assert ledger["attestation_claimed"] is False
    assert ledger["section_7_signed"] is False
    assert checklist_map["production_signoff_claimed"] is False
    assert checklist_map["sections"]["7"]["signed_required"] is False

    collected = {}
    for entry in ledger["entries"]:
        collected.update(entry.get("honesty", {}))
    for flag in mapping["required_honesty_flags"]:
        assert flag in collected or flag in (
            "production_signoff_claimed",
            "section_7_signed",
        ), flag
        if flag in collected:
            assert collected[flag] is False
        if flag == "production_signoff_claimed":
            assert checklist_map["production_signoff_claimed"] is False
        if flag == "section_7_signed":
            # present on cutover / ledger top-level
            assert ledger["section_7_signed"] is False or collected.get("section_7_signed") is False


def test_attestation_evidence_schema_not_forged():
    assert EVIDENCE_EXAMPLE.is_file()
    example = json.loads(EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
    assert example["passed"] is False
    assert example["attestation_claimed"] is False
    assert example["section_7_signed"] is False
    assert example["sections_1_3_verified"] is False
    for field in (
        "attestation_id",
        "started_at",
        "finished_at",
        "environment",
        "ledger_honesty_reviewed",
        "cutover_completed",
        "engineering_name",
        "operations_name",
        "product_name",
        "operator",
        "notes",
    ):
        assert field in example, field
    assert "forged" in example["notes"].lower() or "schema example" in example["notes"].lower()
    assert "ATTESTATION_PACK_MVP" in example["notes"] or "Stage 30 A1" in example["notes"]


def test_launch_sections_remain_unsigned_and_pack_doc():
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

    doc = _read("docs/ATTESTATION_PACK_MVP.md")
    assert "Stage 30 A1" in doc
    assert "test_attestation_pack_a1.py" in doc
    assert "attestation-matrix.json" in doc
    assert "attestation-evidence.example.json" in doc
    assert "EVIDENCE_LEDGER_MVP.md" in doc
    assert "LAUNCH_CERT_MVP.md" in doc
    assert "not" in doc.lower()
    assert "§7" in doc or "Sign-off" in doc
    assert "stage30_a1_attestation_pack.json" in doc

    launch_cert = _read("docs/LAUNCH_CERT_MVP.md")
    assert "Stage 30 A1" in launch_cert or "ATTESTATION_PACK_MVP.md" in launch_cert

    ledger_doc = _read("docs/EVIDENCE_LEDGER_MVP.md")
    assert "Stage 30 A1" in ledger_doc or "ATTESTATION_PACK_MVP.md" in ledger_doc


def test_a1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_30_PLAN.md")
    a1_line = [ln for ln in plan.splitlines() if "| **A1** |" in ln][0]
    assert "COMPLETE" in a1_line
    assert "test_attestation_pack_a1.py" in plan
    assert (
        "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H30x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_attestation_pack_a1.py" in launch
    assert "Stage 30 A1" in launch
    assert "ATTESTATION_PACK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 30 A1" in roadmap
    assert "test_attestation_pack_a1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 30 A1" in pr
    assert "test_attestation_pack_a1.py" in pr or "ATTESTATION_PACK_MVP.md" in pr

    ops = _read("ops/launch/README.md")
    assert "Stage 30 A1" in ops or "attestation-matrix.json" in ops
    assert "ATTESTATION_PACK_MVP.md" in ops

    mapping = json.loads(MATRIX.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "30",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/ATTESTATION_PACK_MVP.md",
        "matrix": "ops/launch/attestation-matrix.json",
        "evidence_schema": "ops/launch/attestation-evidence.example.json",
        "evidence_ledger": "ops/evidence/ledger.json",
        "attestation_claimed": False,
        "section_7_signed": False,
        "sections_1_3_verified": False,
        "packaging_complete": True,
        "gates": mapping["gates"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["attestation_claimed"] is False
    assert loaded["section_7_signed"] is False
    assert loaded["packaging_complete"] is True
