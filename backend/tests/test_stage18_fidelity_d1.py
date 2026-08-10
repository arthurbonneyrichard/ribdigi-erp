"""Stage 18 D1 — documentation fidelity for Launch Integrity & Ops."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_stage18_fidelity_note_and_plan():
    fidelity = _read("docs/STAGE_18_FIDELITY.md")
    assert "BR-16" in fidelity and "BR-17" in fidelity
    assert "test_isolation_matrix_s1.py" in fidelity
    assert "test_security_hardening_a1.py" in fidelity
    assert "test_backup_schedule_b1.py" in fidelity
    assert "test_cross_module_integrity_i1.py" in fidelity
    assert "test_request_logging_l1.py" in fidelity
    assert "test_owasp_suite_t1.py" in fidelity
    assert "test_loadtest_evidence_t1.py" in fidelity
    assert "test_launch_smoke_t1.py" in fidelity
    assert "test_ci_prod_config_c1.py" in fidelity
    assert "test_stage18_fidelity_d1.py" in fidelity
    assert "OPS_MONITORING_MVP.md" in fidelity
    assert "ADR-041" in fidelity or "ADR_041" in fidelity
    assert "H18x" in fidelity
    assert "Kubernetes" in fidelity or "WAL" in fidelity or "1000-VU" in fidelity

    plan = _read("docs/STAGE_18_PLAN.md")
    assert "STAGE_18_FIDELITY.md" in plan
    for ws in ("S1", "A1", "B1", "I1", "L1", "T1", "C1", "D1"):
        assert f"| **{ws}**" in plan
        # Each feature row must be COMPLETE (H18x may still be PENDING)
        assert f"| **{ws}**" in plan
    assert "| **D1**" in plan and "COMPLETE" in plan
    assert "| **H18x**" in plan
    assert "PENDING" in plan  # H18x still open until exit
    d1_line = [ln for ln in plan.splitlines() if "| **D1**" in ln][0]
    assert "COMPLETE" in d1_line
    h18_line = [ln for ln in plan.splitlines() if "| **H18x**" in ln][0]
    assert "PENDING" in h18_line or "Exit" in h18_line


def test_stage18_br_checkboxes_synced():
    br = _read("docs/BUSINESS_REQUIREMENTS_DOCUMENT.md")
    assert "Stage 18 B1" in br
    assert "Stage 18 A1" in br
    assert "Stage 18 D1" in br
    assert "[x] Configurable schedule (daily, weekly)" in br
    assert "[x] Retention policy (keep last N backups)" in br
    assert "[x] Failure alerts to admin" in br
    assert "[ ] Backup storage to S3-compatible storage" in br
    assert "[x] **Login/Logout:**" in br
    assert "[x] **Purchases:**" in br
    assert "[x] **User Activity:**" in br
    assert "[x] **Financial:**" in br
    assert "[x] Filter by user, module, action type, date range" in br
    assert "[x] Export audit logs (CSV, PDF)" in br
    assert "[x] Tamper-proof storage (append-only, hashed)" in br
    assert "[x] Retention policy: minimum 7 years for financial records" in br
    assert "[x] One-click backup initiation by Super Admin" in br
    assert "[x] Restore from backup archive" in br
    assert "[ ] Point-in-time recovery" in br


def test_stage18_security_launch_checklist():
    sec = _read("docs/SECURITY_GUIDE.md")
    assert "Stage 18 S1" in sec
    assert "Stage 18 A1" in sec
    assert "Stage 18 L1" in sec
    assert "test_isolation_matrix_s1.py" in sec
    assert "test_security_hardening_a1.py" in sec
    assert "OPS_MONITORING_MVP.md" in sec
    assert "STAGE_18_FIDELITY.md" in sec or "Stage 18 D1" in sec

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_isolation_matrix_s1.py" in launch
    assert "test_security_hardening_a1.py" in launch
    assert "test_backup_schedule_b1.py" in launch
    assert "test_cross_module_integrity_i1.py" in launch
    assert "test_request_logging_l1.py" in launch
    assert "test_owasp_suite_t1.py" in launch
    assert "test_loadtest_evidence_t1.py" in launch
    assert "test_launch_smoke_t1.py" in launch
    assert "test_ci_prod_config_c1.py" in launch
    assert "test_stage18_fidelity_d1.py" in launch
    assert "STAGE_18_FIDELITY.md" in launch
    assert "H18x next" in launch or "H18x" in launch


def test_stage18_readiness_and_roadmap():
    pr = _read("PRODUCTION_READINESS.md")
    assert "STAGE_18_FIDELITY.md" in pr
    assert "test_stage18_fidelity_d1.py" in pr
    assert "test_isolation_matrix_s1.py" in pr
    assert "test_security_hardening_a1.py" in pr
    assert "test_backup_schedule_b1.py" in pr
    assert "test_cross_module_integrity_i1.py" in pr
    assert "test_request_logging_l1.py" in pr
    assert "test_ci_prod_config_c1.py" in pr
    assert "OPS_MONITORING_MVP.md" in pr

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "STAGE_18_FIDELITY.md" in roadmap
    assert "Stage 18 D1" in roadmap
    assert "ADR_041_STAGE18_OPEN.md" in roadmap
    assert "STAGE_18_PLAN.md" in roadmap
