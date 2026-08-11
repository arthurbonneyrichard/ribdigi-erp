"""Stage 68 T1 — Tenant Company console honesty (not module re-Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "tenant-company-console.json"
HOUSE = ROOT / "ops" / "mvp" / "ribdigi-house-console.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage68_t1_tenant_company_console.json"

REQUIRED_IDS = {
    "tc-owner-outline",
    "tc-shell-core",
    "tc-shell-finance",
    "tc-shell-reports-settings",
    "tc-principal-isolation",
    "tc-house-adjacency",
    "tc-tenancy",
    "tc-plan-honesty",
    "tc-reclaim-remaining",
    "tc-golive-remaining",
}
REQUIRED_CATEGORIES = {"tenant", "honesty"}
REQUIRED_SHELL_LABELS = {
    "POS",
    "Sales",
    "Inventory",
    "Purchasing",
    "Accounting",
    "Expenses",
    "Credit",
    "Tax",
    "Reports",
    "Company",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_tenant_company_console_register_honest():
    assert REGISTER.is_file()
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert mapping["stage"] == "68"
    assert mapping["workstream"] == "T1"
    assert mapping["packaging_complete"] is True
    assert mapping["tenant_modules_reclaimed_complete"] is False
    assert mapping["demo_tenant_claimed"] is False
    assert mapping["cross_principal_leak_claimed"] is False
    assert mapping["go_live_claimed"] is False
    assert mapping["section_7_signed"] is False
    assert mapping["billing_complete_claimed"] is False
    assert mapping["doc"] == "docs/TENANT_COMPANY_CONSOLE_MVP.md"
    assert "stage68_t1_tenant_company_console.json" in mapping["evidence_artifact"]
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
    assert any(s["id"] == "tc-reclaim-remaining" and s["status"] == "remaining" for s in steps)
    assert any(s["id"] == "tc-golive-remaining" and s["status"] == "remaining" for s in steps)
    assert any(
        "module" in d.lower() or "demo" in d.lower() or "go-live" in d.lower() or "tenant" in d.lower()
        for d in mapping["deferred"]
    )
    for rel in (
        mapping["stage68_plan"],
        mapping["adr137"],
        mapping["adr001"],
        mapping["house_console_doc"],
        mapping["house_console"],
        mapping["tenant_shell"],
        mapping["platform_shell"],
        mapping["launch_checklist"],
    ):
        assert (ROOT / rel).is_file(), rel


def test_tenant_company_console_aligns_sources():
    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    house = json.loads(HOUSE.read_text(encoding="utf-8"))
    assert mapping["tenant_modules_reclaimed_complete"] is False
    assert mapping["demo_tenant_claimed"] is False
    for key in ("billing_complete_claimed", "go_live_claimed", "section_7_signed"):
        if key in house:
            assert house[key] is False
    for step in mapping["steps"]:
        assert step["done"] is False
    shell = _read("frontend/components/Shell.tsx")
    for label in REQUIRED_SHELL_LABELS:
        assert label in shell, label
    plan = _read("docs/STAGE_68_PLAN.md")
    assert "TENANT COMPANY" in plan or "Tenant Company" in plan
    assert "POS" in plan and "Sales" in plan


def test_tenant_company_console_doc_and_readme():
    doc = _read("docs/TENANT_COMPANY_CONSOLE_MVP.md")
    assert "Stage 68 T1" in doc
    assert "test_tenant_company_console_t1.py" in doc
    assert "tenant-company-console.json" in doc
    assert "tenant_modules_reclaimed_complete" in doc or "done: false" in doc
    assert "not" in doc.lower()

    readme = _read("ops/mvp/README.md")
    assert "Stage 68 T1" in readme
    assert "TENANT_COMPANY_CONSOLE_MVP.md" in readme
    assert "tenant-company-console.json" in readme


def test_t1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_68_PLAN.md")
    t1_line = [ln for ln in plan.splitlines() if "| **T1** |" in ln][0]
    assert "COMPLETE" in t1_line
    assert "test_tenant_company_console_t1.py" in plan
    assert (
        "T1 next" in plan
        or "T1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H68x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_tenant_company_console_t1.py" in launch
    assert "Stage 68 T1" in launch
    assert "TENANT_COMPANY_CONSOLE_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 68 T1" in roadmap
    assert "test_tenant_company_console_t1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 68 T1" in pr
    assert "test_tenant_company_console_t1.py" in pr or "TENANT_COMPANY_CONSOLE_MVP.md" in pr

    mapping = json.loads(REGISTER.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "68",
        "workstream": "T1",
        "passed": True,
        "doc": "docs/TENANT_COMPANY_CONSOLE_MVP.md",
        "register": "ops/mvp/tenant-company-console.json",
        "packaging_complete": True,
        "tenant_modules_reclaimed_complete": False,
        "demo_tenant_claimed": False,
        "go_live_claimed": False,
        "section_7_signed": False,
        "step_count": len(mapping["steps"]),
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["tenant_modules_reclaimed_complete"] is False
    assert loaded["demo_tenant_claimed"] is False
    assert loaded["step_count"] >= 10
