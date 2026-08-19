"""Stage 51 D1 — documentation fidelity for Commercial Marketplace & Add-Ons."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage51_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_51_FIDELITY.md")
    assert (
        "Marketplace" in fidelity
        or "Add-On" in fidelity
        or "Add-on" in fidelity
        or "addon" in fidelity.lower()
    )
    for name in (
        "test_marketplace_presence_m1.py",
        "test_addon_services_a1.py",
        "test_stage51_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-107" in fidelity or "ADR_107" in fidelity
    assert "H51x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "marketplace" in fidelity.lower()
        or "add-on" in fidelity.lower()
        or "addon" in fidelity.lower()
    )

    plan = _read("docs/STAGE_51_PLAN.md")
    assert "STAGE_51_FIDELITY.md" in plan
    for ws in ("M1", "A1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h51 = [ln for ln in plan.splitlines() if "| **H51x** |" in ln][0]
    assert "PENDING" in h51 or "COMPLETE" in h51
    assert "ADR-107" in plan or "ADR_107" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H51x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage51_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_51_FIDELITY.md" in br
    assert "Stage 51 D1" in br or "test_stage51_fidelity_d1.py" in br
    assert (
        "Stage 51 M1" in br
        or "MARKETPLACE_PRESENCE_MVP.md" in br
        or "Stage 51 A1" in br
        or "ADDON_SERVICES_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_51_FIDELITY.md" in fidelity_tail or "Stage 51 D1" in fidelity_tail

    for rel in (
        "docs/MARKETPLACE_PRESENCE_MVP.md",
        "docs/ADDON_SERVICES_MVP.md",
    ):
        assert _read(rel)


def test_stage51_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 51 D1" in api or "STAGE_51_FIDELITY.md" in api
    assert "test_stage51_fidelity_d1.py" in api or "STAGE_51_FIDELITY.md" in api
    assert (
        "MARKETPLACE_PRESENCE_MVP.md" in api
        or "test_marketplace_presence_m1.py" in api
        or "Stage 51 M1" in api
    )
    assert (
        "ADDON_SERVICES_MVP.md" in api
        or "test_addon_services_a1.py" in api
        or "Stage 51 A1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 51 D1" in deploy or "STAGE_51_FIDELITY.md" in deploy
    assert (
        "MARKETPLACE_PRESENCE_MVP.md" in deploy
        or "Stage 51 M1" in deploy
        or "ADDON_SERVICES_MVP.md" in deploy
        or "Stage 51 A1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 51 D1" in sec or "STAGE_51_FIDELITY.md" in sec
    assert "test_marketplace_presence_m1.py" in sec or "MARKETPLACE_PRESENCE_MVP.md" in sec
    assert "test_addon_services_a1.py" in sec or "ADDON_SERVICES_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_marketplace_presence_m1.py" in launch
    assert "test_addon_services_a1.py" in launch
    assert "test_stage51_fidelity_d1.py" in launch
    assert "STAGE_51_FIDELITY.md" in launch
    assert "ADR-107" in launch or "ADR_107" in launch or "STAGE_51_PLAN.md" in launch


def test_stage51_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_51_FIDELITY.md" in pr
    assert "test_stage51_fidelity_d1.py" in pr
    assert "Stage 51 D1" in pr
    assert "Stage 51 M1" in pr
    assert "Stage 51 A1" in pr
    assert (
        "marketplace_listing_live" in pr
        or "addon_catalog_live" in pr
        or "addon_billing_claimed" in pr
        or "app_store_presence_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_51_FIDELITY.md" in roadmap
    assert "Stage 51 D1" in roadmap
    assert "ADR_107_STAGE51_OPEN.md" in roadmap
    assert "STAGE_51_PLAN.md" in roadmap
    assert "test_stage51_fidelity_d1.py" in roadmap
