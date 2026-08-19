"""Stage 135 D1 — documentation fidelity for Purchase Return / SMS / Stores Transfer Export."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage135_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_135_FIDELITY.md")
    assert (
        "return" in fidelity.lower()
        or "sms" in fidelity.lower()
        or "transfer" in fidelity.lower()
    )
    for name in (
        "test_stage135_returns_export_r1.py",
        "test_stage135_sms_settings_export_s1.py",
        "test_stage135_stores_transfers_t1.py",
        "test_stage135_fidelity_d1.py",
    ):
        assert name in fidelity, name
    assert "ADR-276" in fidelity or "ADR_276" in fidelity
    assert "H135x" in fidelity
    plan = _read("docs/STAGE_135_PLAN.md")
    assert "STAGE_135_FIDELITY.md" in plan
    for ws in ("R1", "S1", "T1", "D1"):
        assert "COMPLETE" in [ln for ln in plan.splitlines() if f"| **{ws}** |" in ln][0], ws


def test_stage135_br16_and_workstream_docs():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "STAGE_135_FIDELITY.md" in br
    assert "Stage 135 D1" in br or "test_stage135_fidelity_d1.py" in br
    assert "Stage 135 R1" in br or "Stage 135 S1" in br or "Stage 135 T1" in br
    fidelity_tail = br.split("#### BR-16.3 Database Restore", 1)[1]
    for stop in ("### 4.17", "### BR-17", "## BR-17", "#### BR-17"):
        if stop in fidelity_tail:
            fidelity_tail = fidelity_tail.split(stop, 1)[0]
            break
    assert "STAGE_135_FIDELITY.md" in fidelity_tail or "Stage 135 D1" in fidelity_tail


def test_stage135_api_deploy_security_launch():
    api = _read("docs/API_DOCUMENTATION.md")
    assert "Stage 135 D1" in api or "STAGE_135_FIDELITY.md" in api
    deploy = _read("docs/DEPLOYMENT_GUIDE.md")
    assert "Stage 135 D1" in deploy or "STAGE_135_FIDELITY.md" in deploy
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 135 D1" in sec or "STAGE_135_FIDELITY.md" in sec
    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_stage135_returns_export_r1.py" in launch
    assert "test_stage135_sms_settings_export_s1.py" in launch
    assert "test_stage135_stores_transfers_t1.py" in launch
    assert "test_stage135_fidelity_d1.py" in launch
    assert "STAGE_135_FIDELITY.md" in launch
    manual = _read("docs/USER_MANUAL.md")
    assert (
        "Purchase Return" in manual
        or "returns/export" in manual
        or "SMS" in manual
        or "settings/sms/export" in manual
        or "stores/transfers/export" in manual
        or "Inter-store" in manual
    )


def test_stage135_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_135_FIDELITY.md" in pr and "test_stage135_fidelity_d1.py" in pr
    assert "Stage 135 D1" in pr and "Stage 135 R1" in pr and "Stage 135 S1" in pr and "Stage 135 T1" in pr
    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_135_FIDELITY.md" in roadmap and "Stage 135 D1" in roadmap
    assert "ADR_276_STAGE135_OPEN.md" in roadmap and "STAGE_135_PLAN.md" in roadmap
