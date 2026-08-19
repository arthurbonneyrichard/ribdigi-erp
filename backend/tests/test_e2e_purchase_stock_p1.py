"""Stage 35 P1 — E2E purchase-to-stock (not live purchasing Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-purchase-stock.json"
ORG = ROOT / "ops" / "mvp" / "e2e-org-bootstrap.json"
USERS = ROOT / "ops" / "mvp" / "e2e-users-rbac.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_p1_e2e_purchase_stock.json"

REQUIRED_IDS = {
    "ps-create-supplier",
    "ps-create-products",
    "ps-create-po",
    "ps-receive-grn",
    "ps-verify-stock",
    "ps-purchase-invoice",
    "ps-tenant-isolation",
    "ps-doc-numbering",
    "ps-po-kanban-deferred",
    "ps-live-purchasing-remaining",
}
REQUIRED_CATEGORIES = {"supplier", "products", "purchasing", "inventory", "security", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_purchase_stock_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "P1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_purchase_stock_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["po_kanban_claimed"] is False
    assert mapping["doc"] == "docs/E2E_PURCHASE_STOCK_MVP.md"
    assert "stage35_p1_e2e_purchase_stock.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "ps-po-kanban-deferred" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "ps-verify-stock" for s in steps)
    assert any(
        "purchase" in d.lower() or "kanban" in d.lower() or "demo" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["e2e_org_bootstrap"],
        mapping["e2e_users_rbac"],
        mapping["stage11_plan"],
        mapping["stage24_plan"],
        mapping["launch_checklist"],
        mapping["api_docs"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_purchase_stock_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    org = json.loads(ORG.read_text(encoding="utf-8"))
    users = json.loads(USERS.read_text(encoding="utf-8"))
    assert org["e2e_smoke_executed_claimed"] is False
    assert org["demo_tenant_claimed"] is False
    assert users["e2e_smoke_executed_claimed"] is False
    assert users["demo_tenant_claimed"] is False
    assert mapping["live_purchase_stock_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["po_kanban_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    stage24 = _read("docs/STAGE_24_PLAN.md")
    assert "Kanban" in stage24 or "kanban" in stage24.lower()


def test_e2e_purchase_stock_doc_and_readme():
    doc = _read("docs/E2E_PURCHASE_STOCK_MVP.md")
    assert "Stage 35 P1" in doc
    assert "test_e2e_purchase_stock_p1.py" in doc
    assert "e2e-purchase-stock.json" in doc
    assert "stage35_p1_e2e_purchase_stock.json" in doc
    assert "live_purchase_stock_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "Kanban" in doc or "kanban" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 P1" in readme
    assert "E2E_PURCHASE_STOCK_MVP.md" in readme
    assert "e2e-purchase-stock.json" in readme


def test_p1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    p1_line = [ln for ln in plan.splitlines() if "| **P1** |" in ln][0]
    assert "COMPLETE" in p1_line
    assert "test_e2e_purchase_stock_p1.py" in plan
    assert (
        "P1 next" in plan
        or "P1 complete" in plan
        or "S1 next" in plan
        or "S1 complete" in plan
        or "V1 next" in plan
        or "V1 complete" in plan
        or "R1 next" in plan
        or "R1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H35x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_purchase_stock_p1.py" in launch
    assert "Stage 35 P1" in launch
    assert "E2E_PURCHASE_STOCK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 P1" in roadmap
    assert "test_e2e_purchase_stock_p1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 P1" in pr
    assert "test_e2e_purchase_stock_p1.py" in pr or "E2E_PURCHASE_STOCK_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "P1",
        "passed": True,
        "doc": "docs/E2E_PURCHASE_STOCK_MVP.md",
        "register": "ops/mvp/e2e-purchase-stock.json",
        "packaging_complete": True,
        "live_purchase_stock_claimed": False,
        "e2e_smoke_executed_claimed": False,
        "demo_tenant_claimed": False,
        "po_kanban_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_purchase_stock_claimed"] is False
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["po_kanban_claimed"] is False
    assert loaded["step_count"] >= 10
