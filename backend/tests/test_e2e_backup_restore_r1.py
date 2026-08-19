"""Stage 35 R1 — E2E backup + restore (not live restore Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-backup-restore.json"
VERIFY = ROOT / "ops" / "mvp" / "e2e-verify-financials.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_r1_e2e_backup_restore.json"

REQUIRED_IDS = {
    "br-create-backup",
    "br-checksum",
    "br-dry-run",
    "br-apply-restore",
    "br-verify",
    "br-schedule",
    "br-tenant-isolation",
    "br-audit",
    "br-pitr-deferred",
    "br-live-remaining",
}
REQUIRED_CATEGORIES = {"backup", "restore", "security", "audit", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_backup_restore_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "R1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_backup_restore_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["live_pitr_drill_claimed"] is False
    assert mapping["doc"] == "docs/E2E_BACKUP_RESTORE_MVP.md"
    assert "stage35_r1_e2e_backup_restore.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "br-pitr-deferred" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "br-apply-restore" for s in steps)
    assert any(
        "restore" in d.lower() or "pitr" in d.lower() or "demo" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["e2e_verify_financials"],
        mapping["logical_runbook"],
        mapping["pitr_drill_pack"],
        mapping["wal_pitr_runbook"],
        mapping["pitr_checklist"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_backup_restore_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert verify["e2e_smoke_executed_claimed"] is False
    assert verify["demo_tenant_claimed"] is False
    assert mapping["live_backup_restore_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["live_pitr_drill_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    runbook = _read("docs/DR_LOGICAL_BACKUP_RUNBOOK.md")
    assert "confirm_text" in runbook or "RESTORE" in runbook
    pitr = _read("docs/PITR_DRILL_PACK_MVP.md")
    assert (
        "live" in pitr.lower()
        and (
            "operator_pitr_drill_executed" in pitr
            or "not" in pitr.lower()
            or "claimed" in pitr.lower()
        )
    )


def test_e2e_backup_restore_doc_and_readme():
    doc = _read("docs/E2E_BACKUP_RESTORE_MVP.md")
    assert "Stage 35 R1" in doc
    assert "test_e2e_backup_restore_r1.py" in doc
    assert "e2e-backup-restore.json" in doc
    assert "stage35_r1_e2e_backup_restore.json" in doc
    assert "live_backup_restore_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "PITR" in doc or "pitr" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 R1" in readme
    assert "E2E_BACKUP_RESTORE_MVP.md" in readme
    assert "e2e-backup-restore.json" in readme


def test_r1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    r1_line = [ln for ln in plan.splitlines() if "| **R1** |" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_e2e_backup_restore_r1.py" in plan
    assert (
        "R1 next" in plan
        or "R1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H35x" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_backup_restore_r1.py" in launch
    assert "Stage 35 R1" in launch
    assert "E2E_BACKUP_RESTORE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 R1" in roadmap
    assert "test_e2e_backup_restore_r1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 R1" in pr
    assert "test_e2e_backup_restore_r1.py" in pr or "E2E_BACKUP_RESTORE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "R1",
        "passed": True,
        "doc": "docs/E2E_BACKUP_RESTORE_MVP.md",
        "register": "ops/mvp/e2e-backup-restore.json",
        "packaging_complete": True,
        "live_backup_restore_claimed": False,
        "e2e_smoke_executed_claimed": False,
        "demo_tenant_claimed": False,
        "live_pitr_drill_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_backup_restore_claimed"] is False
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["live_pitr_drill_claimed"] is False
    assert loaded["step_count"] >= 10
