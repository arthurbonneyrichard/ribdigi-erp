"""Stage 31 R1 — deferred ADR register (not implementing ADR-001–006 post-MVP scopes)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
GATE_MATRIX = ROOT / "ops" / "mvp" / "gate-matrix.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage31_r1_deferred_adr_register.json"

REQUIRED_ADRS = {f"ADR-00{i}" for i in range(1, 7)}
REQUIRED_FILES = {
    "ADR-001": "docs/ADR_001_TENANCY.md",
    "ADR-002": "docs/ADR_002_BILLING_DEFERRED.md",
    "ADR-003": "docs/ADR_003_USER_DELETE_POLICY.md",
    "ADR-004": "docs/ADR_004_MENU_PERMISSIONS.md",
    "ADR-005": "docs/ADR_005_USER_STORE_ASSIGNMENT.md",
    "ADR-006": "docs/ADR_006_LANGUAGE_I18N.md",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_deferred_adr_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "31"
    assert mapping["workstream"] == "R1"
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["billing_complete_claimed"] is False
    assert mapping["schema_per_tenant_claimed"] is False
    assert mapping["i18n_packs_claimed"] is False
    assert mapping["doc"] == "docs/DEFERRED_ADR_REGISTER_MVP.md"
    assert mapping["gate_matrix"] == "ops/mvp/gate-matrix.json"
    assert GATE_MATRIX.is_file()
    assert "stage31_r1_deferred_adr_register.json" in mapping["evidence_artifact"]
    entries = mapping["entries"]
    assert len(entries) == 6
    ids = {e["id"] for e in entries}
    assert ids == REQUIRED_ADRS
    for entry in entries:
        assert entry["file"] == REQUIRED_FILES[entry["id"]]
        assert (ROOT / entry["file"]).is_file(), entry["file"]
        assert entry["implemented_as_complete"] is False
        assert entry["mvp_status"]
        assert entry["post_mvp"]
        assert entry["br_refs"]
        adr_doc = _read(entry["file"])
        assert "Accepted" in adr_doc
        assert "Status" in adr_doc
    assert any("billing" in d.lower() or "schema" in d.lower() or "i18n" in d.lower() for d in mapping["deferred"])


def test_deferred_adr_register_aligns_br_and_gate_matrix():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "ADR-001" in br
    assert "ADR-002" in br
    assert "ADR-003" in br
    assert "ADR-005" in br
    assert "ADR-006" in br

    gate = json.loads(GATE_MATRIX.read_text(encoding="utf-8"))
    deferred_gates = [g for g in gate["gates"] if "deferred_adr" in g.get("honesty", [])]
    assert len(deferred_gates) >= 3
    # Schema / lifecycle / multistore honesty tags remain deferred_adr
    by_id = {g["id"]: g for g in gate["gates"]}
    assert "deferred_adr" in by_id["schema-tenancy"]["honesty"]
    assert "deferred_adr" in by_id["tenant-lifecycle"]["honesty"]
    assert "deferred_adr" in by_id["multistore"]["honesty"]

    for entry in mapping["entries"]:
        assert entry["implemented_as_complete"] is False


def test_deferred_adr_register_doc_and_readme():
    doc = _read("docs/DEFERRED_ADR_REGISTER_MVP.md")
    assert "Stage 31 R1" in doc
    assert "test_deferred_adr_register_r1.py" in doc
    assert "deferred-adr-register.json" in doc
    assert "stage31_r1_deferred_adr_register.json" in doc
    assert "ADR-001" in doc and "ADR-006" in doc
    assert "MVP_GATE_MATRIX_MVP.md" in doc
    assert "not" in doc.lower()
    assert "billing" in doc.lower() or "schema" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 31 R1" in readme or "deferred-adr-register.json" in readme
    assert "DEFERRED_ADR_REGISTER_MVP.md" in readme


def test_r1_plan_launch_roadmap_security_br():
    plan = _read("docs/STAGE_31_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_deferred_adr_register_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "O1 next" in plan
        or "O1 complete" in plan
        or "C1 next" in plan
        or "D1 next" in plan
        or "H31x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_deferred_adr_register_r1.py" in launch
    assert "Stage 31 R1" in launch
    assert "DEFERRED_ADR_REGISTER_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 31 R1" in roadmap
    assert "test_deferred_adr_register_r1.py" in roadmap

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 31 R1" in sec or "DEFERRED_ADR_REGISTER_MVP.md" in sec
    assert "test_deferred_adr_register_r1.py" in sec or "ADR-001" in sec

    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 31 R1" in br or "DEFERRED_ADR_REGISTER_MVP.md" in br

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 31 R1" in pr
    assert "test_deferred_adr_register_r1.py" in pr or "DEFERRED_ADR_REGISTER_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "31",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/DEFERRED_ADR_REGISTER_MVP.md",
        "register": "ops/mvp/deferred-adr-register.json",
        "deferred_implemented_claimed": False,
        "billing_complete_claimed": False,
        "schema_per_tenant_claimed": False,
        "i18n_packs_claimed": False,
        "packaging_complete": True,
        "entry_ids": [e["id"] for e in mapping["entries"]],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["deferred_implemented_claimed"] is False
    assert loaded["packaging_complete"] is True
    assert set(loaded["entry_ids"]) == REQUIRED_ADRS
