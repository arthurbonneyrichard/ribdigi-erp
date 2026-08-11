"""Stage 35 D1 — documentation fidelity for Commercial E2E Operational Smoke."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage35_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_35_FIDELITY.md")
    assert (
        "Org bootstrap" in fidelity
        or "Operational Smoke" in fidelity
        or "E2E" in fidelity
    )
    for name in (
        "test_e2e_org_bootstrap_t1.py",
        "test_e2e_users_rbac_u1.py",
        "test_e2e_purchase_stock_p1.py",
        "test_e2e_sale_payment_s1.py",
        "test_e2e_verify_financials_v1.py",
        "test_e2e_backup_restore_r1.py",
        "test_stage35_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-075" in fidelity or "ADR_075" in fidelity
    assert "H35x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "demo" in fidelity.lower()
        or "e2e_smoke" in fidelity.lower()
    )

    plan = _read("docs/STAGE_35_PLAN.md")
    assert "STAGE_35_FIDELITY.md" in plan
    for ws in ("T1", "U1", "P1", "S1", "V1", "R1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h35 = [ln for ln in plan.splitlines() if "| **H35x** |" in ln][0]
    assert "PENDING" in h35 or "COMPLETE" in h35
    assert "ADR-075" in plan or "ADR_075" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H35x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage35_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_35_FIDELITY.md" in br
    assert "Stage 35 D1" in br or "test_stage35_fidelity_d1.py" in br
    assert (
        "Stage 35 T1" in br
        or "E2E_ORG_BOOTSTRAP_MVP.md" in br
        or "Stage 35 R1" in br
        or "E2E_BACKUP_RESTORE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_35_FIDELITY.md" in fidelity_tail or "Stage 35 D1" in fidelity_tail

    for rel in (
        "docs/E2E_ORG_BOOTSTRAP_MVP.md",
        "docs/E2E_USERS_RBAC_MVP.md",
        "docs/E2E_PURCHASE_STOCK_MVP.md",
        "docs/E2E_SALE_PAYMENT_MVP.md",
        "docs/E2E_VERIFY_FINANCIALS_MVP.md",
        "docs/E2E_BACKUP_RESTORE_MVP.md",
    ):
        assert _read(rel)


def test_stage35_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 35 D1" in api or "STAGE_35_FIDELITY.md" in api
    assert "test_stage35_fidelity_d1.py" in api or "STAGE_35_FIDELITY.md" in api
    assert (
        "E2E_ORG_BOOTSTRAP_MVP.md" in api
        or "test_e2e_org_bootstrap_t1.py" in api
        or "Stage 35 T1" in api
    )
    assert (
        "E2E_BACKUP_RESTORE_MVP.md" in api
        or "test_e2e_backup_restore_r1.py" in api
        or "Stage 35 R1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 35 D1" in deploy or "STAGE_35_FIDELITY.md" in deploy
    assert (
        "E2E_ORG_BOOTSTRAP_MVP.md" in deploy
        or "Stage 35 T1" in deploy
        or "E2E_BACKUP_RESTORE_MVP.md" in deploy
        or "Stage 35 R1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 35 D1" in sec or "STAGE_35_FIDELITY.md" in sec
    assert "test_e2e_users_rbac_u1.py" in sec or "E2E_USERS_RBAC_MVP.md" in sec
    assert "test_e2e_backup_restore_r1.py" in sec or "E2E_BACKUP_RESTORE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_e2e_org_bootstrap_t1.py" in launch
    assert "test_e2e_backup_restore_r1.py" in launch
    assert "test_stage35_fidelity_d1.py" in launch
    assert "STAGE_35_FIDELITY.md" in launch
    assert "ADR-075" in launch or "ADR_075" in launch or "STAGE_35_PLAN.md" in launch


def test_stage35_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_35_FIDELITY.md" in pr
    assert "test_stage35_fidelity_d1.py" in pr
    assert "Stage 35 D1" in pr
    assert "Stage 35 T1" in pr
    assert "Stage 35 R1" in pr
    assert (
        "e2e_smoke_executed_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_35_FIDELITY.md" in roadmap
    assert "Stage 35 D1" in roadmap
    assert "ADR_075_STAGE35_OPEN.md" in roadmap
    assert "STAGE_35_PLAN.md" in roadmap
    assert "test_stage35_fidelity_d1.py" in roadmap
