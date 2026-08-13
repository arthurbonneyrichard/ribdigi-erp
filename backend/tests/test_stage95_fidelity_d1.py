"""Stage 95 D1 — documentation fidelity for Tenant MVP Navigation Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage95_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_95_FIDELITY.md")
    assert "Navigation" in fidelity
    for name in (
        "test_stage95_shell_ia_n1.py",
        "test_stage95_party_stock_p1.py",
        "test_stage95_chrome_c1.py",
        "test_stage95_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-196" in fidelity or "ADR_196" in fidelity
    assert "H95x" in fidelity
    plan = _read("docs/STAGE_95_PLAN.md")
    assert "STAGE_95_FIDELITY.md" in plan
    for ws in ("N1", "P1", "C1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws
    h95 = [ln for ln in plan.splitlines() if "| **H95x** |" in ln][0]
    assert "PENDING" in h95 or "COMPLETE" in h95
    assert any(x in plan for x in ("D1 next", "D1 complete", "H95x next", "Closed", "exit met"))


def test_stage95_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_95_FIDELITY.md" in br
    assert "Stage 95 D1" in br or "test_stage95_fidelity_d1.py" in br
    assert "Stage 95 N1" in br or "Stage 95 P1" in br or "Stage 95 C1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_95_FIDELITY.md" in fidelity_tail or "Stage 95 D1" in fidelity_tail


def test_stage95_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 95 D1" in api or "STAGE_95_FIDELITY.md" in api
    assert "test_stage95_fidelity_d1.py" in api or "STAGE_95_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 95 D1" in deploy or "STAGE_95_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 95 D1" in sec or "STAGE_95_FIDELITY.md" in sec
    assert "test_stage95_shell_ia_n1.py" in sec or "User Management" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage95_shell_ia_n1.py" in launch
    assert "test_stage95_party_stock_p1.py" in launch
    assert "test_stage95_chrome_c1.py" in launch
    assert "test_stage95_fidelity_d1.py" in launch
    assert "STAGE_95_FIDELITY.md" in launch
    assert "ADR-196" in launch or "ADR_196" in launch or "STAGE_95_PLAN.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert "User Management" in manual
    # Stage 162 N1 approved parents supersede Stage 95 Commerce/Operations chrome in the manual.
    assert "People" in manual
    assert ("Finance & Accounts" in manual) or ("Finance" in manual)
    assert ("Inventory" in manual and "Stock" in manual) or ("Commerce" in manual)


def test_stage95_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_95_FIDELITY.md" in pr and "test_stage95_fidelity_d1.py" in pr
    assert "Stage 95 D1" in pr and "Stage 95 N1" in pr and "Stage 95 P1" in pr and "Stage 95 C1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_95_FIDELITY.md" in roadmap and "Stage 95 D1" in roadmap
    assert "ADR_196_STAGE95_OPEN.md" in roadmap and "STAGE_95_PLAN.md" in roadmap
    assert "test_stage95_fidelity_d1.py" in roadmap
