"""Stage 35 U1 — E2E users + RBAC (not live provisioning Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-users-rbac.json"
ORG = ROOT / "ops" / "mvp" / "e2e-org-bootstrap.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_u1_e2e_users_rbac.json"

REQUIRED_IDS = {
    "ur-create-admin",
    "ur-create-manager",
    "ur-create-inventory",
    "ur-create-cashier",
    "ur-assign-roles",
    "ur-rbac-smoke-cashier",
    "ur-tenant-header-403",
    "ur-menu-adr004",
    "ur-store-membership-deferred",
    "ur-live-provisioning-remaining",
}
REQUIRED_CATEGORIES = {"users", "rbac", "security", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_users_rbac_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "U1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_users_provisioned_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["store_membership_claimed"] is False
    assert mapping["doc"] == "docs/E2E_USERS_RBAC_MVP.md"
    assert "stage35_u1_e2e_users_rbac.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ur-store-membership-deferred" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ur-rbac-smoke-cashier" for s in steps)
    assert any("provision" in d.lower() or "ADR-005" in d or "demo" in d.lower() for d in mapping["deferred"])
    for rel in (
        mapping["e2e_org_bootstrap"],
        mapping["security_guide"],
        mapping["stage21_plan"],
        mapping["adr_004"],
        mapping["adr_005"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_users_rbac_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    org = json.loads(ORG.read_text(encoding="utf-8"))
    assert org["e2e_smoke_executed_claimed"] is False
    assert org["demo_tenant_claimed"] is False
    assert org["live_bootstrap_claimed"] is False
    assert mapping["live_users_provisioned_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["store_membership_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    adr005 = _read("docs/ADR_005_USER_STORE_ASSIGNMENT.md")
    assert "deferred" in adr005.lower() or "Deferred" in adr005


def test_e2e_users_rbac_doc_and_readme():
    doc = _read("docs/E2E_USERS_RBAC_MVP.md")
    assert "Stage 35 U1" in doc
    assert "test_e2e_users_rbac_u1.py" in doc
    assert "e2e-users-rbac.json" in doc
    assert "stage35_u1_e2e_users_rbac.json" in doc
    assert "SECURITY_GUIDE.md" in doc
    assert "ADR_005" in doc or "ADR-005" in doc
    assert "live_users_provisioned_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 U1" in readme
    assert "E2E_USERS_RBAC_MVP.md" in readme
    assert "e2e-users-rbac.json" in readme


def test_u1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    u1_line = [ln for ln in plan.splitlines() if "| **U1** |" in ln][0]
    assert "COMPLETE" in u1_line
    assert "test_e2e_users_rbac_u1.py" in plan
    assert (
        "U1 next" in plan
        or "U1 complete" in plan
        or "P1 next" in plan
        or "P1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "V1 next" in plan
        or "V1 complete" in plan
        or "R1 next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_users_rbac_u1.py" in launch
    assert "Stage 35 U1" in launch
    assert "E2E_USERS_RBAC_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 U1" in roadmap
    assert "test_e2e_users_rbac_u1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 U1" in pr
    assert "test_e2e_users_rbac_u1.py" in pr or "E2E_USERS_RBAC_MVP.md" in pr

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 35 U1" in sec
    assert "E2E_USERS_RBAC_MVP.md" in sec or "test_e2e_users_rbac_u1.py" in sec

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "U1",
        "passed": True,
        "doc": "docs/E2E_USERS_RBAC_MVP.md",
        "register": "ops/mvp/e2e-users-rbac.json",
        "packaging_complete": True,
        "live_users_provisioned_claimed": False,
        "e2e_smoke_executed_claimed": False,
        "demo_tenant_claimed": False,
        "store_membership_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_users_provisioned_claimed"] is False
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["store_membership_claimed"] is False
    assert loaded["step_count"] >= 10
