"""Stage 30 L1 — operator evidence ledger (not live-run certificate)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "ops" / "evidence" / "ledger.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage30_l1_evidence_ledger.json"

REQUIRED_IDS = {
    "26-m1",
    "26-w1",
    "26-k1",
    "26-c1",
    "27-b1",
    "27-p1",
    "27-s1",
    "27-l1",
    "28-r1",
    "28-g1",
    "28-a1",
    "28-c1",
    "29-v1",
    "29-b2",
    "29-t1",
    "29-x1",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_evidence_ledger_honest():
    assert LEDGER.is_file()
    mapping = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "30"
    assert mapping["workstream"] == "L1"
    assert mapping["live_runs_certified"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/EVIDENCE_LEDGER_MVP.md"
    assert "stage30_l1_evidence_ledger.json" in mapping["evidence_artifact"]
    entries = mapping["entries"]
    assert len(entries) >= 16
    ids = {e["id"] for e in entries}
    assert REQUIRED_IDS.issubset(ids)
    for entry in entries:
        assert entry["artifact"].startswith("/opt/cursor/artifacts/")
        assert entry["pack_doc"].startswith("docs/")
        assert entry["test"].startswith("backend/tests/")
        assert (ROOT / entry["pack_doc"]).is_file(), entry["pack_doc"]
        assert (ROOT / entry["test"]).is_file(), entry["test"]
        if "checklist" in entry:
            assert (ROOT / entry["checklist"]).is_file(), entry["checklist"]
        for flag, value in entry.get("honesty", {}).items():
            assert value is False, f"{entry['id']}.{flag}"
    # At least one Stage 28 and Stage 29 honesty cluster
    assert any(e["id"].startswith("28-") and e.get("honesty") for e in entries)
    assert any(e["id"].startswith("29-") and e.get("honesty") for e in entries)
    assert any("live" in d.lower() or "§7" in d or "attestation" in d.lower() for d in mapping["deferred"])


def test_ledger_honesty_aligned_with_source_checklists():
    mapping = json.loads(LEDGER.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in mapping["entries"]}

    pairs = [
        ("28-r1", "ops/postgres/pitr-drill-checklist.json"),
        ("28-c1", "ops/loadtest/1000vu-cert-checklist.json"),
        ("29-v1", "ops/security/pentest-engagement-checklist.json"),
        ("29-b2", "ops/postgres/pgbouncer-soak-checklist.json"),
        ("29-t1", "ops/k8s/tls-checklist.json"),
        ("29-x1", "ops/launch/cutover-checklist.json"),
        ("27-l1", "ops/launch/checklist-map.json"),
    ]
    for eid, checklist_rel in pairs:
        entry = by_id[eid]
        checklist = json.loads((ROOT / checklist_rel).read_text(encoding="utf-8"))
        for flag, value in entry["honesty"].items():
            assert flag in checklist, f"{eid} missing {flag} in {checklist_rel}"
            assert checklist[flag] is False
            assert value is False


def test_evidence_ledger_mvp_doc():
    doc = _read("docs/EVIDENCE_LEDGER_MVP.md")
    assert "Stage 30 L1" in doc
    assert "test_evidence_ledger_l1.py" in doc
    assert "ledger.json" in doc
    assert "stage30_l1_evidence_ledger.json" in doc
    assert "not" in doc.lower()
    assert "Stage 26" in doc and "Stage 29" in doc

    readme = _read("ops/evidence/README.md")
    assert "Stage 30 L1" in readme
    assert "EVIDENCE_LEDGER_MVP.md" in readme
    assert "ledger.json" in readme


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_30_PLAN.md")
    l1_line = [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_evidence_ledger_l1.py" in plan
    assert (
        "L1 next" in plan
        or "L1 complete" in plan
        or "I1 next" in plan
        or "I1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H30x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_evidence_ledger_l1.py" in launch
    assert "Stage 30 L1" in launch
    assert "EVIDENCE_LEDGER_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 30 L1" in roadmap
    assert "test_evidence_ledger_l1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 30 L1" in pr
    assert "test_evidence_ledger_l1.py" in pr or "EVIDENCE_LEDGER_MVP.md" in pr
    assert "live_runs_certified" in pr.lower() or "Remaining" in pr or "ledger" in pr.lower()

    ops_launch = _read("ops/launch/README.md")
    assert "Stage 30 L1" in ops_launch or "EVIDENCE_LEDGER_MVP.md" in ops_launch or "ops/evidence" in ops_launch

    mapping = json.loads(LEDGER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "30",
        "workstream": "L1",
        "passed": True,
        "doc": "docs/EVIDENCE_LEDGER_MVP.md",
        "ledger": "ops/evidence/ledger.json",
        "live_runs_certified": False,
        "attestation_claimed": False,
        "section_7_signed": False,
        "packaging_complete": True,
        "entry_count": len(mapping["entries"]),
        "entry_ids": [e["id"] for e in mapping["entries"]],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_runs_certified"] is False
    assert loaded["attestation_claimed"] is False
    assert loaded["packaging_complete"] is True
    assert loaded["entry_count"] >= 16
