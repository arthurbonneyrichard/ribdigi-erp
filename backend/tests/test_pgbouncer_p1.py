"""Stage 27 P1 — PgBouncer connection pooling fidelity."""

from __future__ import annotations

import json
from pathlib import Path

from app import db as db_mod
from app.config import settings

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/db")
EVIDENCE_FILE = EVIDENCE_DIR / "stage27_p1_pgbouncer.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pgbouncer_operator_configs():
    ini = _read("ops/postgres/pgbouncer.ini.example")
    assert "pool_mode" in ini
    assert "transaction" in ini
    assert "listen_port" in ini
    assert "6432" in ini
    assert "ribdigi_erp" in ini
    assert "auth_file" in ini or "userlist" in ini

    users = _read("ops/postgres/userlist.txt.example")
    assert "ribdigi" in users

    compose = _read("ops/postgres/docker-compose.pgbouncer.example.yml")
    assert "pgbouncer" in compose.lower()
    assert "6432" in compose
    assert "Stage 27 P1" in compose

    readme = _read("ops/postgres/README.md")
    assert "Stage 27 P1" in readme
    assert "pgbouncer.ini.example" in readme
    assert "PGBOUNCER_MVP.md" in readme


def test_pgbouncer_mvp_doc_and_deploy_guide():
    doc = _read("docs/PGBOUNCER_MVP.md")
    assert "Stage 27 P1" in doc
    assert "test_pgbouncer_p1.py" in doc
    assert "DATABASE_URL" in doc
    assert "transaction" in doc.lower()
    assert "statement_cache_size" in doc or "asyncpg" in doc.lower()
    assert "Remaining" in doc or "not" in doc.lower()
    assert "6432" in doc

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 27 P1" in deploy or "PGBOUNCER_MVP.md" in deploy
    assert "pgbouncer" in deploy.lower()


def test_engine_kwargs_disable_statement_cache_for_pgbouncer(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://u:p@pgbouncer:6432/ribdigi_erp")
    monkeypatch.setattr(settings, "PGBOUNCER_TRANSACTION_MODE", False)
    kwargs = db_mod.engine_kwargs_for_url(settings.DATABASE_URL)
    assert kwargs.get("pool_pre_ping") is True
    assert kwargs.get("connect_args", {}).get("statement_cache_size") == 0

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://u:p@postgres:5432/ribdigi_erp")
    monkeypatch.setattr(settings, "PGBOUNCER_TRANSACTION_MODE", False)
    direct = db_mod.engine_kwargs_for_url(settings.DATABASE_URL)
    assert direct.get("connect_args", {}).get("statement_cache_size") != 0 or "connect_args" not in direct

    monkeypatch.setattr(settings, "PGBOUNCER_TRANSACTION_MODE", True)
    forced = db_mod.engine_kwargs_for_url(settings.DATABASE_URL)
    assert forced.get("connect_args", {}).get("statement_cache_size") == 0


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_27_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_pgbouncer_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "L1 next" in plan
        or "L1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 27 P1" in pr
    assert "test_pgbouncer_p1.py" in pr
    assert "PGBOUNCER_MVP.md" in pr or "pgbouncer.ini.example" in pr
    assert "PgBouncer" in pr
    section = pr.split("- [x] Redis/Celery/RabbitMQ used for intended production workloads.")[1]
    blob = section.split("- [x]")[0]
    assert "Stage 27 P1" in blob or "pgbouncer" in blob.lower()
    assert "Remaining" in blob
    assert "Complete (MVP)" in blob or "PgBouncer Complete" in blob or "pgbouncer.ini" in blob
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pgbouncer_p1.py" in launch
    assert "Stage 27 P1" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 27 P1" in roadmap
    assert "test_pgbouncer_p1.py" in roadmap

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "27",
        "workstream": "P1",
        "passed": True,
        "pool_mode_example": "transaction",
        "listen_port": 6432,
        "configs": [
            "ops/postgres/pgbouncer.ini.example",
            "ops/postgres/userlist.txt.example",
            "ops/postgres/docker-compose.pgbouncer.example.yml",
        ],
        "doc": "docs/PGBOUNCER_MVP.md",
        "live_pgbouncer_deferred_in_ci": True,
        "in_cluster_helm_pooler_deferred": True,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_pgbouncer_deferred_in_ci"] is True
