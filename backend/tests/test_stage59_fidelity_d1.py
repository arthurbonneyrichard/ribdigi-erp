"""Stage 59 D1 — documentation fidelity for Commercial Channel Extensions."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage59_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_59_FIDELITY.md")
    assert (
        "E-Commerce" in fidelity
        or "Ecommerce" in fidelity
        or "Shopify" in fidelity
        or "CRM" in fidelity
        or "WooCommerce" in fidelity
        or "Channel" in fidelity
    )
    for name in (
        "test_ecommerce_integration_e1.py",
        "test_crm_commercial_c1.py",
        "test_stage59_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-123" in fidelity or "ADR_123" in fidelity
    assert "H59x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "shopify" in fidelity.lower()
        or "crm" in fidelity.lower()
        or "channel" in fidelity.lower()
    )

    plan = _read("docs/STAGE_59_PLAN.md")
    assert "STAGE_59_FIDELITY.md" in plan
    for ws in ("E1", "C1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h59 = [ln for ln in plan.splitlines() if "| **H59x** |" in ln][0]
    assert "PENDING" in h59 or "COMPLETE" in h59
    assert "ADR-123" in plan or "ADR_123" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H59x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage59_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_59_FIDELITY.md" in br
    assert "Stage 59 D1" in br or "test_stage59_fidelity_d1.py" in br
    assert (
        "Stage 59 E1" in br
        or "ECOMMERCE_INTEGRATION_MVP.md" in br
        or "Stage 59 C1" in br
        or "CRM_COMMERCIAL_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_59_FIDELITY.md" in fidelity_tail or "Stage 59 D1" in fidelity_tail

    for rel in (
        "docs/ECOMMERCE_INTEGRATION_MVP.md",
        "docs/CRM_COMMERCIAL_MVP.md",
    ):
        assert _read(rel)


def test_stage59_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 59 D1" in api or "STAGE_59_FIDELITY.md" in api
    assert "test_stage59_fidelity_d1.py" in api or "STAGE_59_FIDELITY.md" in api
    assert (
        "ECOMMERCE_INTEGRATION_MVP.md" in api
        or "test_ecommerce_integration_e1.py" in api
        or "Stage 59 E1" in api
    )
    assert (
        "CRM_COMMERCIAL_MVP.md" in api
        or "test_crm_commercial_c1.py" in api
        or "Stage 59 C1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 59 D1" in deploy or "STAGE_59_FIDELITY.md" in deploy
    assert (
        "ECOMMERCE_INTEGRATION_MVP.md" in deploy
        or "Stage 59 E1" in deploy
        or "CRM_COMMERCIAL_MVP.md" in deploy
        or "Stage 59 C1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 59 D1" in sec or "STAGE_59_FIDELITY.md" in sec
    assert "test_ecommerce_integration_e1.py" in sec or "ECOMMERCE_INTEGRATION_MVP.md" in sec
    assert "test_crm_commercial_c1.py" in sec or "CRM_COMMERCIAL_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_ecommerce_integration_e1.py" in launch
    assert "test_crm_commercial_c1.py" in launch
    assert "test_stage59_fidelity_d1.py" in launch
    assert "STAGE_59_FIDELITY.md" in launch
    assert "ADR-123" in launch or "ADR_123" in launch or "STAGE_59_PLAN.md" in launch


def test_stage59_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_59_FIDELITY.md" in pr
    assert "test_stage59_fidelity_d1.py" in pr
    assert "Stage 59 D1" in pr
    assert "Stage 59 E1" in pr
    assert "Stage 59 C1" in pr
    assert (
        "shopify_connector_live_claimed" in pr
        or "woocommerce_connector_live_claimed" in pr
        or "crm_module_live_claimed" in pr
        or "customer_segmentation_live_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_59_FIDELITY.md" in roadmap
    assert "Stage 59 D1" in roadmap
    assert "ADR_123_STAGE59_OPEN.md" in roadmap
    assert "STAGE_59_PLAN.md" in roadmap
    assert "test_stage59_fidelity_d1.py" in roadmap
