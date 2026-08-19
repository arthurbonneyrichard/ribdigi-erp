"""Stage 123 D1 — documentation fidelity for Inactive Finance Masters, Groups & Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage123_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_123_FIDELITY.md")
    assert "Inactive" in fidelity or "Finance" in fidelity or "Customer" in fidelity
    for name in (
        "test_stage123_inactive_finance_masters_f1.py",
        "test_stage123_inactive_customer_groups_g1.py",
        "test_stage123_finance_party_meta_export_x1.py",
        "test_stage123_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-252" in fidelity or "ADR_252" in fidelity
    assert "H123x" in fidelity
    plan = _read("docs/STAGE_123_PLAN.md")
    assert "STAGE_123_FIDELITY.md" in plan
    for ws in ("F1", "G1", "X1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage123_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_123_FIDELITY.md" in br
    assert "Stage 123 D1" in br or "test_stage123_fidelity_d1.py" in br
    assert "Stage 123 F1" in br or "Stage 123 G1" in br or "Stage 123 X1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_123_FIDELITY.md" in fidelity_tail or "Stage 123 D1" in fidelity_tail


def test_stage123_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 123 D1" in api or "STAGE_123_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 123 D1" in deploy or "STAGE_123_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 123 D1" in sec or "STAGE_123_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage123_inactive_finance_masters_f1.py" in launch
    assert "test_stage123_inactive_customer_groups_g1.py" in launch
    assert "test_stage123_finance_party_meta_export_x1.py" in launch
    assert "test_stage123_fidelity_d1.py" in launch
    assert "STAGE_123_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Inactive Tax Rates" in manual
        or "Inactive Accounts" in manual
        or "Inactive Customer Groups" in manual
        or "accounts/export" in manual
    )


def test_stage123_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_123_FIDELITY.md" in pr and "test_stage123_fidelity_d1.py" in pr
    assert "Stage 123 D1" in pr and "Stage 123 F1" in pr and "Stage 123 G1" in pr and "Stage 123 X1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_123_FIDELITY.md" in roadmap and "Stage 123 D1" in roadmap
    assert "ADR_252_STAGE123_OPEN.md" in roadmap and "STAGE_123_PLAN.md" in roadmap
