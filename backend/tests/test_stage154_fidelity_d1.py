"""Stage 154 D1 — documentation fidelity for PO amendments / batches / API-key usage CSV exports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage154_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_154_FIDELITY.md")
    assert (
        "amendment" in fidelity.lower()
        or "batch" in fidelity.lower()
        or "usage" in fidelity.lower()
    )
    for name in (
        "test_stage154_po_amendments_a1.py",
        "test_stage154_product_batches_k1.py",
        "test_stage154_api_key_usage_u1.py",
        "test_stage154_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-314" in fidelity or "ADR_314" in fidelity
    assert "H154x" in fidelity
    plan = _read("docs/STAGE_154_PLAN.md")
    assert "STAGE_154_FIDELITY.md" in plan
    for ws in ("A1", "K1", "U1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage154_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_154_FIDELITY.md" in br
    assert "Stage 154 D1" in br or "test_stage154_fidelity_d1.py" in br
    assert "Stage 154 A1" in br or "Stage 154 K1" in br or "Stage 154 U1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_154_FIDELITY.md" in fidelity_tail or "Stage 154 D1" in fidelity_tail


def test_stage154_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 154 D1" in api or "STAGE_154_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 154 D1" in deploy or "STAGE_154_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 154 D1" in sec or "STAGE_154_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage154_po_amendments_a1.py" in launch
    assert "test_stage154_product_batches_k1.py" in launch
    assert "test_stage154_api_key_usage_u1.py" in launch
    assert "test_stage154_fidelity_d1.py" in launch
    assert "STAGE_154_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "amendments/export" in manual
        or "PO Amendments" in manual
        or "batches/export" in manual
        or "Product Batches" in manual
        or "usage/export" in manual
        or "API-Key Usage" in manual
    )


def test_stage154_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_154_FIDELITY.md" in pr and "test_stage154_fidelity_d1.py" in pr
    assert "Stage 154 D1" in pr and "Stage 154 A1" in pr and "Stage 154 K1" in pr and "Stage 154 U1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_154_FIDELITY.md" in roadmap and "Stage 154 D1" in roadmap
    assert "ADR_314_STAGE154_OPEN.md" in roadmap and "STAGE_154_PLAN.md" in roadmap
