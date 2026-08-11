"""Stage 31 O1 — operator Remaining register (not forged live runs)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
LEDGER = ROOT / "ops" / "evidence" / "ledger.json"
ATTESTATION = ROOT / "ops" / "launch" / "attestation-matrix.json"
INCIDENT = ROOT / "ops" / "incident" / "incident-checklist.json"
SUPPORT = ROOT / "ops" / "support" / "admin-ops-map.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage31_o1_operator_remaining.json"

REQUIRED_FLAGS = {
    "production_signoff_claimed",
    "operator_pitr_drill_executed",
    "live_staging_apply_claimed",
    "hosted_grafana_claimed",
    "operator_1000vu_executed",
    "vendor_pen_test_purchased",
    "live_soak_executed",
    "letsencrypt_issued",
    "production_cutover_claimed",
    "section_7_signed",
    "pagerduty_hosted_claimed",
    "oncall_rota_live",
    "incident_drill_executed",
    "live_ops_success_claimed",
    "support_sla_claimed",
    "attestation_claimed",
    "sections_1_3_verified",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_operator_remaining_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "31"
    assert mapping["workstream"] == "O1"
    assert mapping["live_runs_certified"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["sections_1_3_verified"] is False
    assert mapping["doc"] == "docs/OPERATOR_REMAINING_MVP.md"
    assert mapping["evidence_ledger"] == "ops/evidence/ledger.json"
    assert mapping["attestation_matrix"] == "ops/launch/attestation-matrix.json"
    assert mapping["incident_checklist"] == "ops/incident/incident-checklist.json"
    assert mapping["support_map"] == "ops/support/admin-ops-map.json"
    assert "stage31_o1_operator_remaining.json" in mapping["evidence_artifact"]
    flags = mapping["flags"]
    assert len(flags) >= 20
    names = {f["flag"] for f in flags}
    assert REQUIRED_FLAGS.issubset(names)
    for item in flags:
        assert item["value"] is False, item["flag"]
        assert item["source"]
        assert item["pack_doc"].startswith("docs/")
        assert (ROOT / item["pack_doc"]).is_file(), item["pack_doc"]
    assert any("live" in d.lower() or "§7" in d or "attestation" in d.lower() for d in mapping["deferred"])


def test_operator_remaining_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    attestation = json.loads(ATTESTATION.read_text(encoding="utf-8"))
    incident = json.loads(INCIDENT.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT.read_text(encoding="utf-8"))

    collected = {}
    for entry in ledger["entries"]:
        collected.update(entry.get("honesty", {}))
    collected["attestation_claimed"] = attestation["attestation_claimed"]
    collected["sections_1_3_verified"] = attestation["sections_1_3_verified"]
    collected["section_7_signed"] = attestation["section_7_signed"] or ledger["section_7_signed"]
    collected["pagerduty_hosted_claimed"] = incident["pagerduty_hosted_claimed"]
    collected["oncall_rota_live"] = incident["oncall_rota_live"]
    collected["incident_drill_executed"] = incident["incident_drill_executed"]
    collected["live_ops_success_claimed"] = support["live_ops_success_claimed"]
    collected["support_sla_claimed"] = support["support_sla_claimed"]

    for item in mapping["flags"]:
        flag = item["flag"]
        assert flag in collected, flag
        assert collected[flag] is False
        assert item["value"] is False

    assert ledger["live_runs_certified"] is False
    assert attestation["attestation_claimed"] is False


def test_operator_remaining_doc_and_readme():
    doc = _read("docs/OPERATOR_REMAINING_MVP.md")
    assert "Stage 31 O1" in doc
    assert "test_operator_remaining_o1.py" in doc
    assert "operator-remaining-register.json" in doc
    assert "stage31_o1_operator_remaining.json" in doc
    assert "EVIDENCE_LEDGER_MVP.md" in doc
    assert "ATTESTATION_PACK_MVP.md" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 31 O1" in readme or "operator-remaining-register.json" in readme
    assert "OPERATOR_REMAINING_MVP.md" in readme


def test_o1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_31_PLAN.md")
    o1_line = [ln for ln in plan.splitlines() if "| **O1** |" in ln][0]
    assert "COMPLETE" in o1_line
    assert "test_operator_remaining_o1.py" in plan
    assert (
        "O1 next" in plan
        or "O1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "H31x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_operator_remaining_o1.py" in launch
    assert "Stage 31 O1" in launch
    assert "OPERATOR_REMAINING_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 31 O1" in roadmap
    assert "test_operator_remaining_o1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 31 O1" in pr
    assert "test_operator_remaining_o1.py" in pr or "OPERATOR_REMAINING_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "31",
        "workstream": "O1",
        "passed": True,
        "doc": "docs/OPERATOR_REMAINING_MVP.md",
        "register": "ops/mvp/operator-remaining-register.json",
        "live_runs_certified": False,
        "attestation_claimed": False,
        "section_7_signed": False,
        "packaging_complete": True,
        "flag_count": len(mapping["flags"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_runs_certified"] is False
    assert loaded["packaging_complete"] is True
