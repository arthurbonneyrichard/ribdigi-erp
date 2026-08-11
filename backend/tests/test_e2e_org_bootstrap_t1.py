"""Stage 35 T1 — E2E org bootstrap (not live bootstrap / demo tenant Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-org-bootstrap.json"
FIRST_TENANT = ROOT / "ops" / "mvp" / "first-tenant-onboarding.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_t1_e2e_org_bootstrap.json"

REQUIRED_IDS = {
    "org-register-tenant",
    "org-verify-email",
    "org-complete-company",
    "org-create-branch",
    "org-create-store",
    "org-create-warehouse",
    "org-verify-links",
    "org-tenant-isolation",
    "org-no-demo",
    "org-live-bootstrap-remaining",
}
REQUIRED_CATEGORIES = {"tenant", "company", "org_unit", "security", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_org_bootstrap_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["live_bootstrap_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["attestation_claimed"] is False
    assert mapping["doc"] == "docs/E2E_ORG_BOOTSTRAP_MVP.md"
    assert "stage35_t1_e2e_org_bootstrap.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "org-live-bootstrap-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "org-no-demo" for s in steps)
    assert any("bootstrap" in d.lower() or "demo" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["first_tenant_onboarding"],
        mapping["launch_checklist"],
        mapping["stage21_plan"],
        mapping["api_docs"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_org_bootstrap_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    first_tenant = json.loads(FIRST_TENANT.read_text(encoding="utf-8"))
    assert first_tenant["first_tenant_onboarded_claimed"] is False
    assert first_tenant["live_onboarding_success_claimed"] is False
    assert first_tenant["demo_tenant_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["live_bootstrap_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False


def test_e2e_org_bootstrap_doc_and_readme():
    doc = _read("docs/E2E_ORG_BOOTSTRAP_MVP.md")
    assert "Stage 35 T1" in doc
    assert "test_e2e_org_bootstrap_t1.py" in doc
    assert "e2e-org-bootstrap.json" in doc
    assert "stage35_t1_e2e_org_bootstrap.json" in doc
    assert "FIRST_TENANT_ONBOARDING_MVP.md" in doc
    assert "branch" in doc.lower() and "warehouse" in doc.lower()
    assert "live_bootstrap_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 T1" in readme
    assert "E2E_ORG_BOOTSTRAP_MVP.md" in readme
    assert "e2e-org-bootstrap.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_e2e_org_bootstrap_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "U1 next" in plan
        or "U1 complete" in plan
        or "P1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_org_bootstrap_t1.py" in launch
    assert "Stage 35 T1" in launch
    assert "E2E_ORG_BOOTSTRAP_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 T1" in roadmap
    assert "test_e2e_org_bootstrap_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 T1" in pr
    assert "test_e2e_org_bootstrap_t1.py" in pr or "E2E_ORG_BOOTSTRAP_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/E2E_ORG_BOOTSTRAP_MVP.md",
        "register": "ops/mvp/e2e-org-bootstrap.json",
        "packaging_complete": True,
        "e2e_smoke_executed_claimed": False,
        "live_bootstrap_claimed": False,
        "demo_tenant_claimed": False,
        "go_live_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["live_bootstrap_claimed"] is False
    assert loaded["demo_tenant_claimed"] is False
    assert loaded["step_count"] >= 10
