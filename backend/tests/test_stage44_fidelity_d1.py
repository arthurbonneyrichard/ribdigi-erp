"""Stage 44 D1 — documentation fidelity for Commercial Data Trust."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage44_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_44_FIDELITY.md")
    assert (
        "Data Trust" in fidelity
        or "Residency" in fidelity
        or "Encryption" in fidelity
        or "key" in fidelity.lower()
    )
    for name in (
        "test_data_residency_r1.py",
        "test_encryption_kms_e1.py",
        "test_stage44_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-093" in fidelity or "ADR_093" in fidelity
    assert "H44x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "residency" in fidelity.lower()
        or "Vault" in fidelity
        or "HSM" in fidelity
    )

    plan = _read("docs/STAGE_44_PLAN.md")
    assert "STAGE_44_FIDELITY.md" in plan
    for ws in ("R1", "E1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h44 = [ln for ln in plan.splitlines() if "| **H44x** |" in ln][0]
    assert "PENDING" in h44 or "COMPLETE" in h44
    assert "ADR-093" in plan or "ADR_093" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H44x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage44_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_44_FIDELITY.md" in br
    assert "Stage 44 D1" in br or "test_stage44_fidelity_d1.py" in br
    assert (
        "Stage 44 R1" in br
        or "DATA_RESIDENCY_MVP.md" in br
        or "Stage 44 E1" in br
        or "ENCRYPTION_KMS_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_44_FIDELITY.md" in fidelity_tail or "Stage 44 D1" in fidelity_tail

    for rel in (
        "docs/DATA_RESIDENCY_MVP.md",
        "docs/ENCRYPTION_KMS_MVP.md",
    ):
        assert _read(rel)


def test_stage44_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 44 D1" in api or "STAGE_44_FIDELITY.md" in api
    assert "test_stage44_fidelity_d1.py" in api or "STAGE_44_FIDELITY.md" in api
    assert (
        "DATA_RESIDENCY_MVP.md" in api
        or "test_data_residency_r1.py" in api
        or "Stage 44 R1" in api
    )
    assert (
        "ENCRYPTION_KMS_MVP.md" in api
        or "test_encryption_kms_e1.py" in api
        or "Stage 44 E1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 44 D1" in deploy or "STAGE_44_FIDELITY.md" in deploy
    assert (
        "DATA_RESIDENCY_MVP.md" in deploy
        or "Stage 44 R1" in deploy
        or "ENCRYPTION_KMS_MVP.md" in deploy
        or "Stage 44 E1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 44 D1" in sec or "STAGE_44_FIDELITY.md" in sec
    assert "test_data_residency_r1.py" in sec or "DATA_RESIDENCY_MVP.md" in sec
    assert "test_encryption_kms_e1.py" in sec or "ENCRYPTION_KMS_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_data_residency_r1.py" in launch
    assert "test_encryption_kms_e1.py" in launch
    assert "test_stage44_fidelity_d1.py" in launch
    assert "STAGE_44_FIDELITY.md" in launch
    assert "ADR-093" in launch or "ADR_093" in launch or "STAGE_44_PLAN.md" in launch


def test_stage44_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_44_FIDELITY.md" in pr
    assert "test_stage44_fidelity_d1.py" in pr
    assert "Stage 44 D1" in pr
    assert "Stage 44 R1" in pr
    assert "Stage 44 E1" in pr
    assert (
        "multi_region_residency_claimed" in pr
        or "hsm_claimed" in pr
        or "vault_saas_live" in pr
        or "customer_managed_keys_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_44_FIDELITY.md" in roadmap
    assert "Stage 44 D1" in roadmap
    assert "ADR_093_STAGE44_OPEN.md" in roadmap
    assert "STAGE_44_PLAN.md" in roadmap
    assert "test_stage44_fidelity_d1.py" in roadmap
