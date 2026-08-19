"""Stage 62 D1 — documentation fidelity for Commercial IoT & AI Marketplace."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage62_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_62_FIDELITY.md")
    assert (
        "IoT" in fidelity
        or "iot" in fidelity.lower()
        or "marketplace" in fidelity.lower()
        or "AI model" in fidelity
        or "smart" in fidelity.lower()
    )
    for name in (
        "test_iot_integration_i1.py",
        "test_ai_model_marketplace_a1.py",
        "test_stage62_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-129" in fidelity or "ADR_129" in fidelity
    assert "H62x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "iot" in fidelity.lower()
        or "marketplace" in fidelity.lower()
        or "smart" in fidelity.lower()
    )

    plan = _read("docs/STAGE_62_PLAN.md")
    assert "STAGE_62_FIDELITY.md" in plan
    for ws in ("I1", "A1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h62 = [ln for ln in plan.splitlines() if "| **H62x** |" in ln][0]
    assert "PENDING" in h62 or "COMPLETE" in h62
    assert "ADR-129" in plan or "ADR_129" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H62x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage62_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_62_FIDELITY.md" in br
    assert "Stage 62 D1" in br or "test_stage62_fidelity_d1.py" in br
    assert (
        "Stage 62 I1" in br
        or "IOT_INTEGRATION_MVP.md" in br
        or "Stage 62 A1" in br
        or "AI_MODEL_MARKETPLACE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_62_FIDELITY.md" in fidelity_tail or "Stage 62 D1" in fidelity_tail

    for rel in (
        "docs/IOT_INTEGRATION_MVP.md",
        "docs/AI_MODEL_MARKETPLACE_MVP.md",
    ):
        assert _read(rel)


def test_stage62_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 62 D1" in api or "STAGE_62_FIDELITY.md" in api
    assert "test_stage62_fidelity_d1.py" in api or "STAGE_62_FIDELITY.md" in api
    assert (
        "IOT_INTEGRATION_MVP.md" in api
        or "test_iot_integration_i1.py" in api
        or "Stage 62 I1" in api
    )
    assert (
        "AI_MODEL_MARKETPLACE_MVP.md" in api
        or "test_ai_model_marketplace_a1.py" in api
        or "Stage 62 A1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 62 D1" in deploy or "STAGE_62_FIDELITY.md" in deploy
    assert (
        "IOT_INTEGRATION_MVP.md" in deploy
        or "Stage 62 I1" in deploy
        or "AI_MODEL_MARKETPLACE_MVP.md" in deploy
        or "Stage 62 A1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 62 D1" in sec or "STAGE_62_FIDELITY.md" in sec
    assert "test_iot_integration_i1.py" in sec or "IOT_INTEGRATION_MVP.md" in sec
    assert "test_ai_model_marketplace_a1.py" in sec or "AI_MODEL_MARKETPLACE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_iot_integration_i1.py" in launch
    assert "test_ai_model_marketplace_a1.py" in launch
    assert "test_stage62_fidelity_d1.py" in launch
    assert "STAGE_62_FIDELITY.md" in launch
    assert "ADR-129" in launch or "ADR_129" in launch or "STAGE_62_PLAN.md" in launch


def test_stage62_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_62_FIDELITY.md" in pr
    assert "test_stage62_fidelity_d1.py" in pr
    assert "Stage 62 D1" in pr
    assert "Stage 62 I1" in pr
    assert "Stage 62 A1" in pr
    assert (
        "iot_integration_live_claimed" in pr
        or "smart_shelves_live_claimed" in pr
        or "ai_model_marketplace_live_claimed" in pr
        or "industry_prediction_marketplace_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_62_FIDELITY.md" in roadmap
    assert "Stage 62 D1" in roadmap
    assert "ADR_129_STAGE62_OPEN.md" in roadmap
    assert "STAGE_62_PLAN.md" in roadmap
    assert "test_stage62_fidelity_d1.py" in roadmap
