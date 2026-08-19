"""Stage 48 T1 — customer training / cert honesty (not live training Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "customer-training-cert.json"
KT = ROOT / "ops" / "mvp" / "knowledge-transfer.json"
SOW = ROOT / "ops" / "mvp" / "professional-services-sow.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage48_t1_customer_training_cert.json"

REQUIRED_IDS = {
    "ct-knowledge-transfer",
    "ct-product-overview",
    "ct-sow-adjacency",
    "ct-first-tenant",
    "ct-support-sla",
    "ct-support-runbook",
    "ct-br-training",
    "ct-plan-honesty",
    "ct-training-remaining",
    "ct-cert-remaining",
}
REQUIRED_CATEGORIES = {"training", "certification", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_customer_training_cert_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "48"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["customer_training_delivered_claimed"] is False
    assert mapping["live_training_claimed"] is False
    assert mapping["training_complete_claimed"] is False
    assert mapping["training_certification_claimed"] is False
    assert mapping["training_attendance_signed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["doc"] == "docs/CUSTOMER_TRAINING_CERT_MVP.md"
    assert "stage48_t1_customer_training_cert.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ct-training-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ct-cert-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "training" in d.lower() or "cert" in d.lower() or "attendance" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["knowledge_transfer"],
        mapping["knowledge_transfer_doc"],
        mapping["product_overview"],
        mapping["professional_services_sow"],
        mapping["professional_services_sow_doc"],
        mapping["first_tenant_onboarding"],
        mapping["first_tenant_onboarding_doc"],
        mapping["support_sla"],
        mapping["support_sla_doc"],
        mapping["support_runbook_doc"],
        mapping["business_requirements"],
        mapping["stage48_plan"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_customer_training_cert_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    kt = json.loads(KT.read_text(encoding="utf-8"))
    sow = json.loads(SOW.read_text(encoding="utf-8"))
    assert mapping["live_training_claimed"] is False
    assert mapping["training_complete_claimed"] is False
    assert kt.get("live_training_claimed") is False
    assert kt.get("training_complete_claimed") is False
    assert sow.get("signed_sow_claimed") is False
    for step in mapping["steps"]:
        assert step["done"] is False
    kt_doc = _read("docs/KNOWLEDGE_TRANSFER_MVP.md")
    assert "training" in kt_doc.lower() or "knowledge" in kt_doc.lower()
    po = _read("docs/PRODUCT_OVERVIEW.md")
    assert "training" in po.lower() or "Onboarding" in po or "Implementation" in po


def test_customer_training_cert_doc_and_readme():
    doc = _read("docs/CUSTOMER_TRAINING_CERT_MVP.md")
    assert "Stage 48 T1" in doc
    assert "test_customer_training_cert_t1.py" in doc
    assert "customer-training-cert.json" in doc
    assert "stage48_t1_customer_training_cert.json" in doc
    assert "live_training_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "training" in doc.lower() or "cert" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 48 T1" in readme
    assert "CUSTOMER_TRAINING_CERT_MVP.md" in readme
    assert "customer-training-cert.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_48_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_customer_training_cert_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H48x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_customer_training_cert_t1.py" in launch
    assert "Stage 48 T1" in launch
    assert "CUSTOMER_TRAINING_CERT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 48 T1" in roadmap
    assert "test_customer_training_cert_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 48 T1" in pr
    assert "test_customer_training_cert_t1.py" in pr or "CUSTOMER_TRAINING_CERT_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "48",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/CUSTOMER_TRAINING_CERT_MVP.md",
        "register": "ops/mvp/customer-training-cert.json",
        "packaging_complete": True,
        "customer_training_delivered_claimed": False,
        "live_training_claimed": False,
        "training_complete_claimed": False,
        "training_certification_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_training_claimed"] is False
    assert loaded["training_complete_claimed"] is False
    assert loaded["step_count"] >= 10
