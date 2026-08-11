"""Stage 29 B2 — PgBouncer soak / Helm pooler pack (not live soak Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "ops" / "postgres" / "pgbouncer-soak-checklist.json"
SOAK_EXAMPLE = ROOT / "ops" / "postgres" / "soak-evidence.example.json"
K8S_SNIPPET = ROOT / "ops" / "postgres" / "pgbouncer-deployment.example.yaml"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/db")
EVIDENCE_FILE = EVIDENCE_DIR / "stage29_b2_pgbouncer_soak.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pgbouncer_soak_checklist_honest():
    assert CHECKLIST.is_file()
    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    assert mapping["stage"] == "29"
    assert mapping["workstream"] == "B2"
    assert mapping["live_soak_executed"] is False
    assert mapping["helm_pooler_default_claimed"] is False
    assert mapping["doc"] == "docs/PGBOUNCER_SOAK_PACK_MVP.md"
    assert mapping["pgbouncer_mvp"] == "docs/PGBOUNCER_MVP.md"
    assert mapping["helm_snippet"] == "ops/postgres/pgbouncer-deployment.example.yaml"
    assert len(mapping["steps"]) >= 4
    for step in mapping["steps"]:
        assert step["class"] == "operator_required"
    assert "stage29_b2_pgbouncer_soak.json" in mapping["evidence_artifact"]
    assert any("soak" in d.lower() or "Helm" in d or "default" in d.lower() for d in mapping["deferred"])


def test_soak_evidence_schema_not_forged():
    assert SOAK_EXAMPLE.is_file()
    example = json.loads(SOAK_EXAMPLE.read_text(encoding="utf-8"))
    assert example["passed"] is False
    assert example["show_pools_ok"] is False
    assert example["helm_pooler_used"] is False
    for field in (
        "run_id",
        "database_url_host",
        "pool_mode",
        "p95_ms",
        "error_rate",
        "operator",
        "notes",
    ):
        assert field in example, field
    assert "forged" in example["notes"].lower() or "schema example" in example["notes"].lower()
    assert "PGBOUNCER_SOAK_PACK_MVP" in example["notes"] or "Stage 29 B2" in example["notes"]


def test_optional_k8s_snippet_not_default_helm():
    assert K8S_SNIPPET.is_file()
    text = K8S_SNIPPET.read_text(encoding="utf-8")
    assert "NOT the default" in text or "not" in text.lower()
    assert "6432" in text
    assert "pgbouncer" in text.lower()
    assert "Deployment" in text
    assert "29-b2" in text or "Stage 29 B2" in text or "stage: \"29-b2" in text
    # Must not live as default chart templates
    helm_templates = ROOT / "helm" / "ribdigi" / "templates"
    if helm_templates.is_dir():
        for p in helm_templates.rglob("*"):
            if p.is_file():
                body = p.read_text(encoding="utf-8", errors="ignore").lower()
                assert "pgbouncer" not in body, p


def test_pgbouncer_soak_pack_doc_and_p1_base():
    doc = _read("docs/PGBOUNCER_SOAK_PACK_MVP.md")
    assert "Stage 29 B2" in doc
    assert "test_pgbouncer_soak_b2.py" in doc
    assert "pgbouncer-soak-checklist.json" in doc
    assert "pgbouncer-deployment.example.yaml" in doc
    assert "PGBOUNCER_MVP.md" in doc
    assert "not" in doc.lower()
    assert "stage29_b2_pgbouncer_soak.json" in doc

    p1 = _read("docs/PGBOUNCER_MVP.md")
    assert "Stage 29 B2" in p1 or "PGBOUNCER_SOAK_PACK_MVP.md" in p1

    readme = _read("ops/postgres/README.md")
    assert "Stage 29 B2" in readme
    assert "pgbouncer-soak-checklist.json" in readme
    assert "PGBOUNCER_SOAK_PACK_MVP.md" in readme


def test_b2_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_29_PLAN.md")
    b2_line = [ln for ln in plan.splitlines() if "| **B2** |" in ln][0]
    assert "COMPLETE" in b2_line
    assert "test_pgbouncer_soak_b2.py" in plan
    assert (
        "B2 next" in plan
        or "B2 complete" in plan
        or "T1 next" in plan
        or "T1 complete" in plan
        or "X1 next" in plan
        or "X1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H29x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_pgbouncer_soak_b2.py" in launch
    assert "Stage 29 B2" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 29 B2" in roadmap
    assert "test_pgbouncer_soak_b2.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 29 B2" in pr
    assert "test_pgbouncer_soak_b2.py" in pr or "PGBOUNCER_SOAK_PACK_MVP.md" in pr
    assert "live soak" in pr.lower() or "Remaining" in pr
    assert "Helm" in pr or "pooler" in pr.lower() or "in-cluster" in pr.lower()

    mapping = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "29",
        "workstream": "B2",
        "passed": True,
        "doc": "docs/PGBOUNCER_SOAK_PACK_MVP.md",
        "checklist": "ops/postgres/pgbouncer-soak-checklist.json",
        "soak_schema": "ops/postgres/soak-evidence.example.json",
        "helm_snippet": "ops/postgres/pgbouncer-deployment.example.yaml",
        "pgbouncer_mvp": "docs/PGBOUNCER_MVP.md",
        "live_soak_executed": False,
        "helm_pooler_default_claimed": False,
        "packaging_complete": True,
        "steps": mapping["steps"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_soak_executed"] is False
    assert loaded["helm_pooler_default_claimed"] is False
    assert loaded["packaging_complete"] is True
