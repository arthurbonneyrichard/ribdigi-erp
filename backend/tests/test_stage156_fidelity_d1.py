"""Stage 156 D1 — documentation fidelity for images / variants / bank-feed settings CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage156_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_156_FIDELITY.md")
    assert (
        "image" in fidelity.lower()
        or "variant" in fidelity.lower()
        or "bank-feed" in fidelity.lower()
        or "bank feed" in fidelity.lower()
    )
    for name in (
        "test_stage156_product_images_g1.py",
        "test_stage156_product_variants_v1.py",
        "test_stage156_bank_feed_settings_f1.py",
        "test_stage156_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-318" in fidelity or "ADR_318" in fidelity
    assert "H156x" in fidelity
    plan = _read("docs/STAGE_156_PLAN.md")
    assert "STAGE_156_FIDELITY.md" in plan
    for ws in ("G1", "V1", "F1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage156_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_156_FIDELITY.md" in br
    assert "Stage 156 D1" in br or "test_stage156_fidelity_d1.py" in br
    assert "Stage 156 G1" in br or "Stage 156 V1" in br or "Stage 156 F1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_156_FIDELITY.md" in fidelity_tail or "Stage 156 D1" in fidelity_tail


def test_stage156_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 156 D1" in api or "STAGE_156_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 156 D1" in deploy or "STAGE_156_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 156 D1" in sec or "STAGE_156_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage156_product_images_g1.py" in launch
    assert "test_stage156_product_variants_v1.py" in launch
    assert "test_stage156_bank_feed_settings_f1.py" in launch
    assert "test_stage156_fidelity_d1.py" in launch
    assert "STAGE_156_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "images/export" in manual
        or "Product Images" in manual
        or "variants/export" in manual
        or "Per-Product Variants" in manual
        or "bank-feed/export" in manual
        or "Bank-Feed Settings" in manual
    )


def test_stage156_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_156_FIDELITY.md" in pr and "test_stage156_fidelity_d1.py" in pr
    assert "Stage 156 D1" in pr and "Stage 156 G1" in pr and "Stage 156 V1" in pr and "Stage 156 F1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_156_FIDELITY.md" in roadmap and "Stage 156 D1" in roadmap
    assert "ADR_318_STAGE156_OPEN.md" in roadmap and "STAGE_156_PLAN.md" in roadmap
