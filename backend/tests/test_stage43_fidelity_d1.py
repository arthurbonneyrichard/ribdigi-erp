"""Stage 43 D1 — documentation fidelity for Commercial Legal Notice."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage43_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_43_FIDELITY.md")
    assert (
        "Legal Notice" in fidelity
        or "ToS" in fidelity
        or "Cookie" in fidelity
        or "privacy" in fidelity.lower()
    )
    for name in (
        "test_tos_aup_t1.py",
        "test_cookie_privacy_notice_c1.py",
        "test_stage43_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-091" in fidelity or "ADR_091" in fidelity
    assert "H43x" in fidelity
    assert (
        "go-live" in fidelity.lower()
        or "§7" in fidelity
        or "Remaining" in fidelity
        or "deferred" in fidelity.lower()
        or "ToS" in fidelity
        or "cookie" in fidelity.lower()
    )

    plan = _read("docs/STAGE_43_PLAN.md")
    assert "STAGE_43_FIDELITY.md" in plan
    for ws in ("T1", "C1", "D1"):
        line = [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0]
        assert "COMPLETE" in line, ws
    h43 = [ln for ln in plan.splitlines() if "| **H43x** |" in ln][0]
    assert "PENDING" in h43 or "COMPLETE" in h43
    assert "ADR-091" in plan or "ADR_091" in plan
    assert (
        "D1 next" in plan
        or "D1 complete" in plan
        or "H43x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )


def test_stage43_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_43_FIDELITY.md" in br
    assert "Stage 43 D1" in br or "test_stage43_fidelity_d1.py" in br
    assert (
        "Stage 43 T1" in br
        or "TOS_AUP_MVP.md" in br
        or "Stage 43 C1" in br
        or "COOKIE_PRIVACY_NOTICE_MVP.md" in br
    )

    assert "#### BR-16.3 Database Restore" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_43_FIDELITY.md" in fidelity_tail or "Stage 43 D1" in fidelity_tail

    for rel in (
        "docs/TOS_AUP_MVP.md",
        "docs/COOKIE_PRIVACY_NOTICE_MVP.md",
    ):
        assert _read(rel)


def test_stage43_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 43 D1" in api or "STAGE_43_FIDELITY.md" in api
    assert "test_stage43_fidelity_d1.py" in api or "STAGE_43_FIDELITY.md" in api
    assert (
        "TOS_AUP_MVP.md" in api
        or "test_tos_aup_t1.py" in api
        or "Stage 43 T1" in api
    )
    assert (
        "COOKIE_PRIVACY_NOTICE_MVP.md" in api
        or "test_cookie_privacy_notice_c1.py" in api
        or "Stage 43 C1" in api
    )

    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 43 D1" in deploy or "STAGE_43_FIDELITY.md" in deploy
    assert (
        "TOS_AUP_MVP.md" in deploy
        or "Stage 43 T1" in deploy
        or "COOKIE_PRIVACY_NOTICE_MVP.md" in deploy
        or "Stage 43 C1" in deploy
    )

    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 43 D1" in sec or "STAGE_43_FIDELITY.md" in sec
    assert "test_tos_aup_t1.py" in sec or "TOS_AUP_MVP.md" in sec
    assert "test_cookie_privacy_notice_c1.py" in sec or "COOKIE_PRIVACY_NOTICE_MVP.md" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_tos_aup_t1.py" in launch
    assert "test_cookie_privacy_notice_c1.py" in launch
    assert "test_stage43_fidelity_d1.py" in launch
    assert "STAGE_43_FIDELITY.md" in launch
    assert "ADR-091" in launch or "ADR_091" in launch or "STAGE_43_PLAN.md" in launch


def test_stage43_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_43_FIDELITY.md" in pr
    assert "test_stage43_fidelity_d1.py" in pr
    assert "Stage 43 D1" in pr
    assert "Stage 43 T1" in pr
    assert "Stage 43 C1" in pr
    assert (
        "tos_signed_claimed" in pr
        or "cookie_consent_live" in pr
        or "clickwrap_live" in pr
        or "cmp_saas_claimed" in pr
        or "go_live_claimed" in pr
        or "§7" in pr
        or "Remaining" in pr
        or "packaging" in pr.lower()
    )

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_43_FIDELITY.md" in roadmap
    assert "Stage 43 D1" in roadmap
    assert "ADR_091_STAGE43_OPEN.md" in roadmap
    assert "STAGE_43_PLAN.md" in roadmap
    assert "test_stage43_fidelity_d1.py" in roadmap
