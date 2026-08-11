"""Stage 32 B1 — post-MVP backlog (not implementing deferred scopes)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "ops" / "mvp" / "post-mvp-backlog.json"
DEFERRED = ROOT / "ops" / "mvp" / "deferred-adr-register.json"
REMAINING = ROOT / "ops" / "mvp" / "operator-remaining-register.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage32_b1_post_mvp_backlog.json"

REQUIRED_ADR_IDS = {f"adr-00{i}" for i in range(1, 7)}
REQUIRED_CATEGORIES = {"deferred_adr", "operator_remaining", "product_deferred"}
REQUIRED_OPS_IDS = {
    "ops-go-live-attestation",
    "ops-live-drills",
    "ops-hosted-saas",
    "ops-vendor-pentest",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_post_mvp_backlog_honest():
    assert BACKLOG.is_file()
    mapping = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert mapping["stage"] == "32"
    assert mapping["workstream"] == "B1"
    assert mapping["backlog_complete"] is True
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["billing_complete_claimed"] is False
    assert mapping["schema_per_tenant_claimed"] is False
    assert mapping["i18n_packs_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["live_runs_certified"] is False
    assert mapping["doc"] == "docs/POST_MVP_BACKLOG_MVP.md"
    assert mapping["deferred_adr_register"] == "ops/mvp/deferred-adr-register.json"
    assert mapping["operator_remaining_register"] == "ops/mvp/operator-remaining-register.json"
    assert "stage32_b1_post_mvp_backlog.json" in mapping["evidence_artifact"]
    items = mapping["items"]
    assert len(items) >= 12
    ids = {i["id"] for i in items}
    assert REQUIRED_ADR_IDS.issubset(ids)
    assert REQUIRED_OPS_IDS.issubset(ids)
    cats = {i["category"] for i in items}
    assert REQUIRED_CATEGORIES.issubset(cats)
    for item in items:
        assert item["status"] == "backlog"
        assert item["implemented_as_complete"] is False
        assert item["title"]
        assert item["source"]
    assert any("billing" in d.lower() or "schema" in d.lower() or "§7" in d for d in mapping["deferred"])
    for rel in (
        mapping["deferred_adr_register"],
        mapping["operator_remaining_register"],
        mapping["release_notes"],
        mapping["mvp_declaration"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_post_mvp_backlog_aligns_registers():
    mapping = json.loads(BACKLOG.read_text(encoding="utf-8"))
    deferred = json.loads(DEFERRED.read_text(encoding="utf-8"))
    remaining = json.loads(REMAINING.read_text(encoding="utf-8"))

    assert deferred["deferred_implemented_claimed"] is False
    assert deferred["billing_complete_claimed"] is False
    assert remaining["live_runs_certified"] is False
    assert remaining["attestation_claimed"] is False
    assert remaining["section_7_signed"] is False
    for entry in deferred["entries"]:
        assert entry["implemented_as_complete"] is False
    for item in mapping["items"]:
        assert item["implemented_as_complete"] is False
    assert mapping["deferred_implemented_claimed"] is False
    assert mapping["go_live_claimed"] is False


def test_post_mvp_backlog_doc_and_readme():
    doc = _read("docs/POST_MVP_BACKLOG_MVP.md")
    assert "Stage 32 B1" in doc
    assert "test_post_mvp_backlog_b1.py" in doc
    assert "post-mvp-backlog.json" in doc
    assert "stage32_b1_post_mvp_backlog.json" in doc
    assert "DEFERRED_ADR_REGISTER_MVP.md" in doc
    assert "OPERATOR_REMAINING_MVP.md" in doc
    assert "deferred_adr" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 32 B1" in readme
    assert "POST_MVP_BACKLOG_MVP.md" in readme
    assert "post-mvp-backlog.json" in readme


def test_b1_plan_launch_roadmap_security_br():
    plan = _read("docs/STAGE_32_PLAN.md")
    b1_line = [ln for ln in plan.splitlines() if "| **B1** |" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_post_mvp_backlog_b1.py" in plan
    assert (
        "B1 next" in plan
        or "B1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H32x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_post_mvp_backlog_b1.py" in launch
    assert "Stage 32 B1" in launch
    assert "POST_MVP_BACKLOG_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 32 B1" in roadmap
    assert "test_post_mvp_backlog_b1.py" in roadmap

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 32 B1" in sec or "POST_MVP_BACKLOG_MVP.md" in sec
    assert "test_post_mvp_backlog_b1.py" in sec or "ADR-001" in sec

    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 32 B1" in br or "POST_MVP_BACKLOG_MVP.md" in br

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 32 B1" in pr
    assert "test_post_mvp_backlog_b1.py" in pr or "POST_MVP_BACKLOG_MVP.md" in pr

    mapping = json.loads(BACKLOG.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "32",
        "workstream": "B1",
        "passed": True,
        "doc": "docs/POST_MVP_BACKLOG_MVP.md",
        "backlog": "ops/mvp/post-mvp-backlog.json",
        "backlog_complete": True,
        "deferred_implemented_claimed": False,
        "billing_complete_claimed": False,
        "go_live_claimed": False,
        "item_count": len(mapping["items"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["deferred_implemented_claimed"] is False
    assert loaded["backlog_complete"] is True
    assert loaded["item_count"] >= 12
