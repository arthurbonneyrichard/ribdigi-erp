"""Stage 26 W1 — WAL / PITR strategy + S3 offsite backup fidelity."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/dr")
EVIDENCE_FILE = EVIDENCE_DIR / "stage26_w1_wal_pitr_strategy.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_wal_postgres_config_examples():
    conf = _read("ops/postgres/postgresql-wal-archive.conf.example")
    assert "wal_level" in conf
    assert "archive_mode" in conf
    assert "archive_command" in conf
    assert "archive_timeout" in conf

    script = _read("ops/postgres/archive-wal-to-s3.sh.example")
    assert "WAL_S3_BUCKET" in script
    assert "s3://" in script
    assert "aws" in script

    readme = _read("ops/postgres/README.md")
    assert "Stage 26 W1" in readme
    assert "DR_WAL_PITR_RUNBOOK.md" in readme


def test_ribbak_offsite_sync_examples():
    sync = _read("ops/backup/sync-ribbak-offsite.sh.example")
    assert "BACKUP_DIR" in sync
    assert ".ribbak" in sync
    assert "BACKUP_OFFSITE_S3_BUCKET" in sync
    assert "s3 sync" in sync or "s3://" in sync

    compose = _read("ops/backup/docker-compose.wal-drill.example.yml")
    assert "postgres" in compose.lower()
    assert "minio" in compose.lower()
    assert "Stage 26 W1" in compose

    readme = _read("ops/backup/README.md")
    assert "Stage 26 W1" in readme
    assert "sync-ribbak-offsite.sh.example" in readme


def test_wal_pitr_runbook():
    doc = _read("docs/DR_WAL_PITR_RUNBOOK.md")
    assert "Stage 26 W1" in doc
    assert "test_wal_pitr_w1.py" in doc
    assert "ops/postgres" in doc
    assert "ops/backup" in doc
    assert "archive_mode" in doc or "WAL" in doc
    assert "PITR" in doc
    assert ".ribbak" in doc
    assert "DR_LOGICAL_BACKUP_RUNBOOK.md" in doc
    assert "operator" in doc.lower()
    assert "Remaining" in doc or "deferred" in doc.lower() or "not CI" in doc.lower()
    assert "stage26_w1_wal_pitr_strategy.json" in doc


def test_logical_runbook_cross_links_wal():
    logical = _read("docs/DR_LOGICAL_BACKUP_RUNBOOK.md")
    assert "DR_WAL_PITR_RUNBOOK.md" in logical or "Stage 26 W1" in logical


def test_wal_gate_complete_mvp_and_evidence():
    pr = _read("PRODUCTION_READINESS.md")
    assert "- [x] Point-in-time recovery/WAL strategy complete." in pr
    assert "- [ ] Point-in-time recovery/WAL strategy complete." not in pr
    assert "Stage 26 W1" in pr
    assert "test_wal_pitr_w1.py" in pr
    assert "DR_WAL_PITR_RUNBOOK.md" in pr
    assert "ops/postgres" in pr
    # Remaining honesty
    assert "operator" in pr.lower() or "staging" in pr.lower() or "Remaining" in pr
    # K8s may be Complete (MVP) after K1; load stays open
    assert (
        "- [ ] Kubernetes production deployment reviewed." in pr
        or (
            "- [x] Kubernetes production deployment reviewed." in pr
            and "Stage 26 K1" in pr
        )
    )
    assert (
        "- [ ] Load/performance tests meet documented targets." in pr
        or (
            "- [x] Load/performance tests meet documented targets." in pr
            and "Stage 26 C1" in pr
        )
    )
    # Monitoring already Complete (MVP) from M1
    assert "- [x] Monitoring, metrics, logging and alerting complete." in pr

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "26",
        "workstream": "W1",
        "passed": True,
        "strategy_documented": True,
        "runbook": "docs/DR_WAL_PITR_RUNBOOK.md",
        "configs": [
            "ops/postgres/postgresql-wal-archive.conf.example",
            "ops/postgres/archive-wal-to-s3.sh.example",
            "ops/backup/sync-ribbak-offsite.sh.example",
        ],
        "logical_dr_complete": True,
        "operator_pitr_drill_required": True,
        "wal_pitr_deferred_in_ci": True,
        "automatic_ribbak_s3_upload": False,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["operator_pitr_drill_required"] is True
    assert loaded["wal_pitr_deferred_in_ci"] is True
    assert loaded["strategy_documented"] is True


def test_w1_plan_launch_roadmap_cite():
    plan = _read("docs/STAGE_26_PLAN.md")
    w1_line = [ln for ln in plan.splitlines() if "| **W1** |" in ln][0]
    assert "COMPLETE" in w1_line
    assert "test_wal_pitr_w1.py" in plan
    assert (
        "W1 next" in plan
        or "W1 complete" in plan
        or "K1 next" in plan
        or "K1 complete" in plan
        or "C1 next" in plan
        or "C1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H26x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_wal_pitr_w1.py" in launch
    assert "Stage 26 W1" in launch or "DR_WAL_PITR_RUNBOOK" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 26 W1" in roadmap
    assert "test_wal_pitr_w1.py" in roadmap
    assert "DR_WAL_PITR_RUNBOOK.md" in roadmap
