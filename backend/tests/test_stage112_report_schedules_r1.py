"""Stage 112 R1 — Report schedule frequency/enabled URL + Shell leaves + #schedules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_report_schedule_leaves_r1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "frequency=daily#schedules" in shell
    assert "frequency=weekly#schedules" in shell
    assert "enabled=true#schedules" in shell
    assert "enabled=false#schedules" in shell
    assert "Daily Report Schedules" in shell
    assert "Enabled Report Schedules" in shell


def test_reports_schedule_url_sync_and_hash_r1():
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "writeScheduleFilters" in reports
    assert "filteredSchedules" in reports
    assert 'id="schedules"' in reports
    assert "scrollIntoView" in reports
    assert "Stage 112" in reports
    assert "Filter schedules by frequency" in reports or 'aria-label="Filter schedules by frequency"' in reports
