"""Stage 33 T1 — knowledge transfer (not live training Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "knowledge-transfer.json"
SUPPORT_MAP = ROOT / "ops" / "support" / "admin-ops-map.json"
HANDOFF = ROOT / "ops" / "mvp" / "operator-handoff.json"
FIRST_TENANT = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage33_t1_knowledge_transfer.json"

REQUIRED_IDS = {
    "kt-continuity-honesty",
    "kt-admin-rbac",
    "kt-first-tenant",
    "kt-support-runbook",
    "kt-operator-handoff",
    "kt-monitoring-incident",
    "kt-backup-dr",
    "kt-launch-cutover",
    "kt-security-isolation",
    "kt-compliance-risk",
}
REQUIRED_AUDIENCES = {"operator_admin", "admin", "support", "operator"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_knowledge_transfer_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "33"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_training_claimed"] is False
    assert mapping["training_complete_claimed"] is False
    assert mapping["support_sla_claimed"] is False
    assert mapping["handoff_complete_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/KNOWLEDGE_TRANSFER_MVP.md"
    assert "stage33_t1_knowledge_transfer.json" in mapping["evidence_artifact"]
    modules = mapping["modules"]
    assert len(modules) >= 10
    ids = {m["id"] for m in modules}
    assert REQUIRED_IDS.issubset(ids)
    audiences = {m["audience"] for m in modules}
    assert REQUIRED_AUDIENCES.issubset(audiences)
    for module in modules:
        assert module["delivered"] is False
        assert module["status"] in ("indexed",)
        assert module["title"]
        assert module["source"]
        assert isinstance(module["pack_refs"], list) and module["pack_refs"]
        for pack in module["pack_refs"]:
            assert (ROOT / pack).is_file(), pack
    assert any(m["id"] == "kt-support-runbook" for m in modules)
    assert any(m["id"] == "kt-operator-handoff" for m in modules)
    assert any("training" in d.lower() or "live" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["support_runbook"],
        mapping["admin_ops_map"],
        mapping["operator_handoff"],
        mapping["first_tenant_onboarding"],
        mapping["admin_manual"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_knowledge_transfer_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    support_map = json.loads(SUPPORT_MAP.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    first_tenant = json.loads(FIRST_TENANT.read_text(encoding="utf-8"))

    assert support_map.get("live_ops_success_claimed") is False
    assert support_map.get("support_sla_claimed") is False
    assert handoff["handoff_complete_claimed"] is False
    assert handoff["go_live_claimed"] is False
    assert first_tenant["first_tenant_onboarded_claimed"] is False
    assert first_tenant["live_onboarding_success_claimed"] is False
    assert mapping["live_training_claimed"] is False
    assert mapping["training_complete_claimed"] is False
    for module in mapping["modules"]:
        assert module["delivered"] is False


def test_knowledge_transfer_doc_and_readme():
    doc = _read("docs/KNOWLEDGE_TRANSFER_MVP.md")
    assert "Stage 33 T1" in doc
    assert "test_knowledge_transfer_t1.py" in doc
    assert "knowledge-transfer.json" in doc
    assert "stage33_t1_knowledge_transfer.json" in doc
    assert "SUPPORT_RUNBOOK_MVP.md" in doc
    assert "OPERATOR_HANDOFF_MVP.md" in doc
    assert "live_training_claimed" in doc or "delivered: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 33 T1" in readme
    assert "KNOWLEDGE_TRANSFER_MVP.md" in readme
    assert "knowledge-transfer.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_33_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_knowledge_transfer_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H33x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_knowledge_transfer_t1.py" in launch
    assert "Stage 33 T1" in launch
    assert "KNOWLEDGE_TRANSFER_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 33 T1" in roadmap
    assert "test_knowledge_transfer_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 33 T1" in pr
    assert "test_knowledge_transfer_t1.py" in pr or "KNOWLEDGE_TRANSFER_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "33",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/KNOWLEDGE_TRANSFER_MVP.md",
        "register": "ops/mvp/knowledge-transfer.json",
        "packaging_complete": True,
        "live_training_claimed": False,
        "training_complete_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "module_count": len(mapping["modules"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_training_claimed"] is False
    assert loaded["training_complete_claimed"] is False
    assert loaded["module_count"] >= 10
