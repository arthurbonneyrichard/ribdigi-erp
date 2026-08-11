"""Stage 32 D1 — documentation fidelity for Commercial MVP Handoff."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage32_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_32_FIDELITY.md")
    assert "Handoff" in fidelity or "Archive" in fidelity or "Backlog" in fidelity
    assert "test_acceptance_archive_a1.py" in fidelity
    assert "test_operator_handoff_h1.py" in fidelity
    assert "test_release_notes_n1.py" in fidelity
    assert "test_post_mvp_backlog_b1.py" in fidelity
    assert "test_stage32_fidelity_d1.py" in fidelity
    assert "ADR-069" in fidelity or "ADR_069" in fidelity
    assert "H32x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "attestation" in fidelity.lower()
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
    )

    plan = _read("docs/STAGE_32_PLAN.md")
    assert "STAGE_32_FIDELITY.md" in plan
    for ws in ("A1", "H1", "N1", "B1", "D1", "H32x"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    assert "ADR-070" in plan or "ADR_070" in plan
    assert "Closed" in plan or "exit met" in plan.lower()
    assert "ADR-070" in fidelity or "ADR_070" in fidelity or "exit met" in fidelity.lower()


def test_stage32_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_32_FIDELITY.md" in br
    assert "Stage 32 D1" in br or "test_stage32_fidelity_d1.py" in br
    assert (
        "Stage 32 A1" in br
        or "ACCEPTANCE_ARCHIVE_MVP.md" in br
        or "Stage 32 B1" in br
        or "POST_MVP_BACKLOG_MVP.md" in br
        or "Stage 32 H1" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_32_FIDELITY.md" in fidelity_tail or "Stage 32 D1" in fidelity_tail

    assert _read("docs/ACCEPTANCE_ARCHIVE_MVP.md")
    assert _read("docs/OPERATOR_HANDOFF_MVP.md")
    assert _read("docs/RELEASE_NOTES_MVP.md")
    assert _read("docs/POST_MVP_BACKLOG_MVP.md")


def test_stage32_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 32 D1" in api or "STAGE_32_FIDELITY.md" in api
    assert "test_stage32_fidelity_d1.py" in api or "STAGE_32_FIDELITY.md" in api
    assert (
        "ACCEPTANCE_ARCHIVE_MVP.md" in api
        or "test_acceptance_archive_a1.py" in api
        or "Stage 32 A1" in api
    )
    assert (
        "OPERATOR_HANDOFF_MVP.md" in api
        or "test_operator_handoff_h1.py" in api
        or "Stage 32 H1" in api
    )
    assert (
        "RELEASE_NOTES_MVP.md" in api
        or "test_release_notes_n1.py" in api
        or "Stage 32 N1" in api
    )
    assert (
        "POST_MVP_BACKLOG_MVP.md" in api
        or "test_post_mvp_backlog_b1.py" in api
        or "Stage 32 B1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 32 D1" in deploy or "STAGE_32_FIDELITY.md" in deploy
    assert (
        "ACCEPTANCE_ARCHIVE_MVP.md" in deploy
        or "Stage 32 A1" in deploy
        or "OPERATOR_HANDOFF_MVP.md" in deploy
        or "RELEASE_NOTES_MVP.md" in deploy
        or "POST_MVP_BACKLOG_MVP.md" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 32 D1" in sec or "STAGE_32_FIDELITY.md" in sec
    assert "test_acceptance_archive_a1.py" in sec or "ACCEPTANCE_ARCHIVE_MVP.md" in sec
    assert "test_operator_handoff_h1.py" in sec or "OPERATOR_HANDOFF_MVP.md" in sec
    assert "test_release_notes_n1.py" in sec or "RELEASE_NOTES_MVP.md" in sec
    assert "test_post_mvp_backlog_b1.py" in sec or "POST_MVP_BACKLOG_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_acceptance_archive_a1.py" in launch
    assert "test_operator_handoff_h1.py" in launch
    assert "test_release_notes_n1.py" in launch
    assert "test_post_mvp_backlog_b1.py" in launch
    assert "test_stage32_fidelity_d1.py" in launch
    assert "STAGE_32_FIDELITY.md" in launch
    assert "STAGE_32_EXIT_CRITERIA.md" in launch or "ADR-070" in launch


def test_stage32_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_32_FIDELITY.md" in pr
    assert "test_stage32_fidelity_d1.py" in pr
    assert "Stage 32 D1" in pr
    assert "Stage 32 A1" in pr
    assert "Stage 32 H1" in pr
    assert "Stage 32 N1" in pr
    assert "Stage 32 B1" in pr
    assert "STAGE_32_EXIT_CRITERIA.md" in pr or "ADR-070" in pr or "ADR_070" in pr
    assert (
        "go_live_claimed" in pr
        or "§7" in pr
        or "attestation" in pr.lower()
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_32_FIDELITY.md" in roadmap
    assert "Stage 32 D1" in roadmap
    assert "ADR_069_STAGE32_OPEN.md" in roadmap
    assert "STAGE_32_PLAN.md" in roadmap
    assert "test_stage32_fidelity_d1.py" in roadmap
    assert "STAGE_32_EXIT_CRITERIA.md" in roadmap
    assert "ADR_070_STAGE32_FREEZE.md" in roadmap
