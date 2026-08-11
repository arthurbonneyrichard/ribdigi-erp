"""Stage 27 L1 — launch certification pack (not fake production sign-off)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP_FILE = ROOT / "ops" / "launch" / "checklist-map.json"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/launch")
EVIDENCE_FILE = EVIDENCE_DIR / "stage27_l1_launch_cert.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section_body(checklist: str, heading: str) -> str:
    """Return markdown body under `## {heading}` until next `## `."""
    marker = f"## {heading}"
    assert marker in checklist, heading
    rest = checklist.split(marker, 1)[1]
    if "\n## " in rest:
        rest = rest.split("\n## ", 1)[0]
    return rest


def _unchecked_items(body: str) -> list[str]:
    return re.findall(r"^- \[ \] (.+)$", body, flags=re.M)


def _checked_items(body: str) -> list[str]:
    return re.findall(r"^- \[x\] (.+)$", body, flags=re.M)


def test_checklist_map_exists_and_honest():
    assert MAP_FILE.is_file()
    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    assert mapping["production_signoff_claimed"] is False
    assert mapping["checklist"] == "docs/LAUNCH_CHECKLIST.md"
    assert mapping["doc"] == "docs/LAUNCH_CERT_MVP.md"
    for sid in ("1", "2", "3", "4", "5", "6", "7"):
        assert sid in mapping["sections"], sid
    assert mapping["sections"]["1"]["class"] == "operator_required"
    assert mapping["sections"]["2"]["class"] == "operator_required"
    assert mapping["sections"]["3"]["class"] == "operator_required"
    assert mapping["sections"]["5"]["class"] == "ci_proven"
    assert mapping["sections"]["6"]["class"] == "deferred"
    assert mapping["sections"]["7"]["class"] == "operator_required"
    assert mapping["sections"]["7"]["signed_required"] is False


def test_operator_sections_remain_unchecked():
    checklist = _read("docs/LAUNCH_CHECKLIST.md")
    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))

    for sid, title in (
        ("1", "1. Configuration & secrets"),
        ("2", "2. Identity & security"),
        ("3", "3. Integrations (Stage 6–7)"),
    ):
        body = _section_body(checklist, title)
        unchecked = _unchecked_items(body)
        assert unchecked, f"section {sid} must keep operator unchecked rows"
        assert mapping["sections"][sid]["unchecked_required"] is True

    smoke = _section_body(checklist, "4. Core ERP smoke (real tenant data)")
    assert any(x.startswith("Product create + stock-in") for x in _unchecked_items(smoke))
    # CI-proven markers still present as checked rows
    for marker in mapping["sections"]["4"]["ci_proven_markers"]:
        assert marker in smoke or marker in checklist, marker

    rel = _section_body(checklist, "5. Reliability & cache")
    assert _checked_items(rel), "§5 should be CI-proven checked"
    assert not _unchecked_items(rel)

    deferred = _section_body(checklist, "6. Explicitly deferred (do not block Stage 7 exit)")
    assert "Vendor penetration" in deferred or "ZAP" in deferred or "1000-VU" in deferred

    signoff = _section_body(checklist, "7. Sign-off")
    # Empty Name/Date cells — not a forged production signature
    assert "| Engineering |" in signoff
    assert re.search(r"\| Engineering \| \| \|", signoff) or "| Engineering | |" in signoff
    assert "remain unchecked until a real environment" in checklist.lower() or "real environment" in checklist.lower()


def test_launch_cert_mvp_doc():
    doc = _read("docs/LAUNCH_CERT_MVP.md")
    assert "Stage 27 L1" in doc
    assert "test_launch_cert_l1.py" in doc
    assert "operator_required" in doc
    assert "ci_proven" in doc
    assert "deferred" in doc
    assert "not" in doc.lower() and "sign-off" in doc.lower()
    assert "checklist-map.json" in doc
    assert "LAUNCH_CHECKLIST.md" in doc


def test_l1_plan_launch_roadmap_readiness():
    plan = _read("docs/STAGE_27_PLAN.md")
    l1_line = [ln for ln in plan.splitlines() if "| **L1** |" in ln][0]
    assert "COMPLETE" in l1_line
    assert "test_launch_cert_l1.py" in plan
    assert (
        "L1 next" in plan
        or "L1 complete" in plan
        or "D1 next" in plan
        or "D1 complete" in plan
        or "Closed" in plan
        or "exit met" in plan.lower()
    )

    launch = _read("docs/LAUNCH_CHECKLIST.md")
    assert "test_launch_cert_l1.py" in launch
    assert "Stage 27 L1" in launch
    assert "LAUNCH_CERT_MVP.md" in launch

    roadmap = _read("docs/DEVELOPMENT_ROADMAP.md")
    assert "Stage 27 L1" in roadmap
    assert "test_launch_cert_l1.py" in roadmap

    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 27 L1" in pr
    assert "test_launch_cert_l1.py" in pr or "LAUNCH_CERT_MVP.md" in pr

    ops = _read("ops/launch/README.md")
    assert "Stage 27 L1" in ops
    assert "checklist-map.json" in ops

    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "27",
        "workstream": "L1",
        "passed": True,
        "doc": "docs/LAUNCH_CERT_MVP.md",
        "map": "ops/launch/checklist-map.json",
        "checklist": "docs/LAUNCH_CHECKLIST.md",
        "production_signoff_claimed": False,
        "sections": mapping["sections"],
        "operator_sections_unchecked": True,
        "signoff_table_unsigned": True,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["production_signoff_claimed"] is False
    assert loaded["operator_sections_unchecked"] is True
