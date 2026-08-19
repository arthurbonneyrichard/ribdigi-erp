"""Stage 30 S1 — support / Admin runbook fidelity (not live ops success)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "ops" / "support" / "admin-ops-map.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage30_s1_support_runbook.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section_body(manual: str, heading: str) -> str:
    assert heading in manual, heading
    rest = manual.split(heading, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def test_admin_ops_map_honest():
    assert MAP.is_file()
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    assert mapping["stage"] == "30"
    assert mapping["workstream"] == "S1"
    assert mapping["live_ops_success_claimed"] is False
    assert mapping["support_sla_claimed"] is False
    assert mapping["doc"] == "docs/SUPPORT_RUNBOOK_MVP.md"
    assert mapping["admin_manual"] == "docs/ADMIN_MANUAL.md"
    assert "stage30_s1_support_runbook.json" in mapping["evidence_artifact"]
    assert len(mapping["sections"]) >= 3
    ids = {s["id"] for s in mapping["sections"]}
    assert {"7", "11", "12"}.issubset(ids)
    for section in mapping["sections"]:
        assert section["admin_heading"].startswith("## ")
        assert len(section["packs"]) >= 2
        for pack in section["packs"]:
            assert (ROOT / pack).is_file(), pack
        for op in section.get("ops", []):
            assert (ROOT / op).is_file(), op
    assert any("SLA" in d or "PITR" in d or "helpdesk" in d.lower() for d in mapping["deferred"])


def test_admin_manual_sections_cite_ops_packs():
    manual = _read("docs/ADMIN_MANUAL.md")
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    assert "Stage 30 S1" in manual
    assert "SUPPORT_RUNBOOK_MVP.md" in manual or "test_support_runbook_s1.py" in manual

    for section in mapping["sections"]:
        body = _section_body(manual, section["admin_heading"])
        assert "Stage 30 S1" in body or "SUPPORT_RUNBOOK" in body or "ops/" in body
        # At least one pack citation lands in the section body
        assert any(Path(p).name in body or p in body for p in section["packs"]), section["id"]
        assert "Remaining" in body or "not" in body.lower() or "packaging" in body.lower()


def test_support_runbook_mvp_doc():
    doc = _read("docs/SUPPORT_RUNBOOK_MVP.md")
    assert "Stage 30 S1" in doc
    assert "test_support_runbook_s1.py" in doc
    assert "admin-ops-map.json" in doc
    assert "ADMIN_MANUAL.md" in doc
    assert "stage30_s1_support_runbook.json" in doc
    assert "not" in doc.lower()
    assert "§7" in doc or "Backup" in doc
    assert "§11" in doc or "Monitoring" in doc
    assert "§12" in doc or "Troubleshooting" in doc

    readme = _read("ops/support/README.md")
    assert "Stage 30 S1" in readme
    assert "SUPPORT_RUNBOOK_MVP.md" in readme


def test_s1_plan_launch_roadmap():
    plan = _read("docs/STAGE_30_PLAN.md")
    s1_line = [ln for ln in plan.splitlines() if "| **S1** |" in ln][0]
    assert "COMPLETE" in s1_line
    assert "test_support_runbook_s1.py" in plan
    assert (
        "S1 next" in plan
        or "S1 complete" in plan
        or "A1 next" in plan
        or "A1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "H30x next" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_support_runbook_s1.py" in launch
    assert "Stage 30 S1" in launch
    assert "SUPPORT_RUNBOOK_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 30 S1" in roadmap
    assert "test_support_runbook_s1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 30 S1" in pr
    assert "test_support_runbook_s1.py" in pr or "SUPPORT_RUNBOOK_MVP.md" in pr

    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "30",
        "workstream": "S1",
        "passed": True,
        "doc": "docs/SUPPORT_RUNBOOK_MVP.md",
        "map": "ops/support/admin-ops-map.json",
        "admin_manual": "docs/ADMIN_MANUAL.md",
        "live_ops_success_claimed": False,
        "support_sla_claimed": False,
        "packaging_complete": True,
        "sections": mapping["sections"],
        "deferred": mapping["deferred"],
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["live_ops_success_claimed"] is False
    assert loaded["support_sla_claimed"] is False
    assert loaded["packaging_complete"] is True
