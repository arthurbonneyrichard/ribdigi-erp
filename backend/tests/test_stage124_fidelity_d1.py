"""Stage 124 D1 — documentation fidelity for Inactive Variants, Roles & Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage124_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_124_FIDELITY.md")
    assert "Inactive" in fidelity or "Variant" in fidelity or "Role" in fidelity
    for name in (
        "test_stage124_inactive_product_variants_v1.py",
        "test_stage124_inactive_custom_roles_r1.py",
        "test_stage124_variant_role_export_x1.py",
        "test_stage124_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-254" in fidelity or "ADR_254" in fidelity
    assert "H124x" in fidelity
    plan = _read("docs/STAGE_124_PLAN.md")
    assert "STAGE_124_FIDELITY.md" in plan
    for ws in ("V1", "R1", "X1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage124_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_124_FIDELITY.md" in br
    assert "Stage 124 D1" in br or "test_stage124_fidelity_d1.py" in br
    assert "Stage 124 V1" in br or "Stage 124 R1" in br or "Stage 124 X1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_124_FIDELITY.md" in fidelity_tail or "Stage 124 D1" in fidelity_tail


def test_stage124_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 124 D1" in api or "STAGE_124_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 124 D1" in deploy or "STAGE_124_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 124 D1" in sec or "STAGE_124_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage124_inactive_product_variants_v1.py" in launch
    assert "test_stage124_inactive_custom_roles_r1.py" in launch
    assert "test_stage124_variant_role_export_x1.py" in launch
    assert "test_stage124_fidelity_d1.py" in launch
    assert "STAGE_124_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Inactive Product Variants" in manual
        or "Inactive Custom Roles" in manual
        or "variants/export" in manual
        or "roles/export" in manual
    )


def test_stage124_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_124_FIDELITY.md" in pr and "test_stage124_fidelity_d1.py" in pr
    assert "Stage 124 D1" in pr and "Stage 124 V1" in pr and "Stage 124 R1" in pr and "Stage 124 X1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_124_FIDELITY.md" in roadmap and "Stage 124 D1" in roadmap
    assert "ADR_254_STAGE124_OPEN.md" in roadmap and "STAGE_124_PLAN.md" in roadmap
