"""Stage 35 S1 — E2E sale-to-payment (not live POS Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "e2e-sale-payment.json"
PURCHASE = ROOT / "ops" / "mvp" / "e2e-purchase-stock.json"
USERS = ROOT / "ops" / "mvp" / "e2e-users-rbac.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage35_s1_e2e_sale_payment.json"

REQUIRED_IDS = {
    "sp-create-customer",
    "sp-pos-sale",
    "sp-receive-payment",
    "sp-verify-stock-reduction",
    "sp-receipt-drawer",
    "sp-insufficient-stock",
    "sp-tenant-isolation",
    "sp-doc-numbering",
    "sp-usb-serial-deferred",
    "sp-live-sale-remaining",
}
REQUIRED_CATEGORIES = {"customer", "pos", "payment", "inventory", "security", "deferred", "honesty"}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e2e_sale_payment_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "35"
    assert mapping["workstream"] == "S1"
    assert mapping["packaging_complete"] is True
    assert mapping["live_sale_payment_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["usb_serial_drivers_claimed"] is False
    assert mapping["doc"] == "docs/E2E_SALE_PAYMENT_MVP.md"
    assert "stage35_s1_e2e_sale_payment.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "sp-usb-serial-deferred" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "sp-verify-stock-reduction" for s in steps)
    assert any(
        "sale" in d.lower() or "pos" in d.lower() or "usb" in d.lower() or "demo" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["e2e_purchase_stock"],
        mapping["e2e_users_rbac"],
        mapping["stage12_plan"],
        mapping["stage13_plan"],
        mapping["stage24_plan"],
        mapping["launch_checklist"],
        mapping["api_docs"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_e2e_sale_payment_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    purchase = json.loads(PURCHASE.read_text(encoding="utf-8"))
    users = json.loads(USERS.read_text(encoding="utf-8"))
    assert purchase["e2e_smoke_executed_claimed"] is False
    assert purchase["demo_tenant_claimed"] is False
    assert users["e2e_smoke_executed_claimed"] is False
    assert mapping["live_sale_payment_claimed"] is False
    assert mapping["e2e_smoke_executed_claimed"] is False
    assert mapping["usb_serial_drivers_claimed"] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    stage24 = _read("docs/STAGE_24_PLAN.md")
    assert "USB" in stage24 or "serial" in stage24.lower()


def test_e2e_sale_payment_doc_and_readme():
    doc = _read("docs/E2E_SALE_PAYMENT_MVP.md")
    assert "Stage 35 S1" in doc
    assert "test_e2e_sale_payment_s1.py" in doc
    assert "e2e-sale-payment.json" in doc
    assert "stage35_s1_e2e_sale_payment.json" in doc
    assert "live_sale_payment_claimed" in doc or "done: false" in doc
    assert "not" in doc.lower()
    assert "USB" in doc or "serial" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 35 S1" in readme
    assert "E2E_SALE_PAYMENT_MVP.md" in readme
    assert "e2e-sale-payment.json" in readme


def test_s1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_35_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_e2e_sale_payment_s1.py" in plan
    assert (
        "S1 next" in plan
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
    assert "test_e2e_sale_payment_s1.py" in launch
    assert "Stage 35 S1" in launch
    assert "E2E_SALE_PAYMENT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 35 S1" in roadmap
    assert "test_e2e_sale_payment_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 35 S1" in pr
    assert "test_e2e_sale_payment_s1.py" in pr or "E2E_SALE_PAYMENT_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "35",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/E2E_SALE_PAYMENT_MVP.md",
        "register": "ops/mvp/e2e-sale-payment.json",
        "packaging_complete": True,
        "live_sale_payment_claimed": False,
        "e2e_smoke_executed_claimed": False,
        "demo_tenant_claimed": False,
        "usb_serial_drivers_claimed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_sale_payment_claimed"] is False
    assert loaded["e2e_smoke_executed_claimed"] is False
    assert loaded["usb_serial_drivers_claimed"] is False
    assert loaded["step_count"] >= 10
