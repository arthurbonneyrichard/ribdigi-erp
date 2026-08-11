"""Stage 37 D1 — documentation fidelity for Commercial Data Protection."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage37_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_37_FIDELITY.md")
    assert (
        "Data Protection" in fidelity
        or "Portability" in fidelity
        or "Erasure" in fidelity
        or "portability" in fidelity
    )
    for name in (
        "test_data_portability_p1.py",
        "test_erasure_honesty_e1.py",
        "test_stage37_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-079" in fidelity or "ADR_079" in fidelity
    assert "H37x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "GDPR" in fidelity
        or "hard-delete" in fidelity.lower()
        or "DSAR" in fidelity
    )

    plan = _read("docs/STAGE_37_PLAN.md")
    assert "STAGE_37_FIDELITY.md" in plan
    for ws in ("P1", "E1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h37 = [ln for ln in plan.splitlines() if "| **H37x** |" in ln][0]
    assert "PENDING" in h37 or "COMPLETE" in h37
    assert "ADR-079" in plan or "ADR_079" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H37x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage37_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_37_FIDELITY.md" in br
    assert "Stage 37 D1" in br or "test_stage37_fidelity_d1.py" in br
    assert (
        "Stage 37 P1" in br
        or "DATA_PORTABILITY_MVP.md" in br
        or "Stage 37 E1" in br
        or "ERASURE_HONESTY_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_37_FIDELITY.md" in fidelity_tail or "Stage 37 D1" in fidelity_tail

    for rel in (
        "docs/DATA_PORTABILITY_MVP.md",
        "docs/ERASURE_HONESTY_MVP.md",
    ):
        assert _read(rel)


def test_stage37_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 37 D1" in api or "STAGE_37_FIDELITY.md" in api
    assert "test_stage37_fidelity_d1.py" in api or "STAGE_37_FIDELITY.md" in api
    assert (
        "DATA_PORTABILITY_MVP.md" in api
        or "test_data_portability_p1.py" in api
        or "Stage 37 P1" in api
    )
    assert (
        "ERASURE_HONESTY_MVP.md" in api
        or "test_erasure_honesty_e1.py" in api
        or "Stage 37 E1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 37 D1" in deploy or "STAGE_37_FIDELITY.md" in deploy
    assert (
        "DATA_PORTABILITY_MVP.md" in deploy
        or "Stage 37 P1" in deploy
        or "ERASURE_HONESTY_MVP.md" in deploy
        or "Stage 37 E1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 37 D1" in sec or "STAGE_37_FIDELITY.md" in sec
    assert "test_data_portability_p1.py" in sec or "DATA_PORTABILITY_MVP.md" in sec
    assert "test_erasure_honesty_e1.py" in sec or "ERASURE_HONESTY_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_data_portability_p1.py" in launch
    assert "test_erasure_honesty_e1.py" in launch
    assert "test_stage37_fidelity_d1.py" in launch
    assert "STAGE_37_FIDELITY.md" in launch
    assert "ADR-079" in launch or "ADR_079" in launch or "STAGE_37_PLAN.md" in launch


def test_stage37_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_37_FIDELITY.md" in pr
    assert "test_stage37_fidelity_d1.py" in pr
    assert "Stage 37 D1" in pr
    assert "Stage 37 P1" in pr
    assert "Stage 37 E1" in pr
    assert (
        "gdpr_complete_claimed" in pr
        or "hard_delete_claimed" in pr
        or "dsar_portal_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_37_FIDELITY.md" in roadmap
    assert "Stage 37 D1" in roadmap
    assert "ADR_079_STAGE37_OPEN.md" in roadmap
    assert "STAGE_37_PLAN.md" in roadmap
    assert "test_stage37_fidelity_d1.py" in roadmap
