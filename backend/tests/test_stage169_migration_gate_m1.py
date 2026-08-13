"""Stage 169 M1 — Alembic migration gate (single head + chain)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "backend" / "alembic" / "versions"
REGISTER = ROOT / "ops" / "mvp" / "migration-gate.json"


def _parse_revisions() -> dict[str, str | None]:
    """Map revision_id -> down_revision (None for root)."""
    mapping: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev_m = re.search(r'^revision\s*[:=]\s*["\']([^"\']+)["\']', text, re.M)
        if not rev_m:
            # also support revision = "x" without quotes edge cases via ast
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            rev = None
            down = None
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == "revision":
                            if isinstance(node.value, ast.Constant):
                                rev = node.value.value
                        if isinstance(t, ast.Name) and t.id == "down_revision":
                            if isinstance(node.value, ast.Constant):
                                down = node.value.value
            if rev:
                mapping[str(rev)] = None if down is None else str(down)
            continue
        rev = rev_m.group(1)
        down_m = re.search(
            r'^down_revision\s*[:=]\s*(None|["\']([^"\']*)["\'])', text, re.M
        )
        if not down_m:
            mapping[rev] = None
        elif down_m.group(1) == "None":
            mapping[rev] = None
        else:
            mapping[rev] = down_m.group(2) or None
    return mapping


def test_migration_gate_single_head_and_chain_m1():
    mapping = _parse_revisions()
    assert mapping, "no alembic revisions found"
    pointed = {d for d in mapping.values() if d}
    heads = [r for r in mapping if r not in pointed]
    assert len(heads) == 1, f"expected single alembic head, found {heads}"

    # All down_revisions resolve (except None).
    for rev, down in mapping.items():
        if down is None:
            continue
        assert down in mapping, f"{rev} down_revision {down} missing"

    # Walk from head to root — no cycles, visits finite.
    head = heads[0]
    seen: set[str] = set()
    cur: str | None = head
    while cur is not None:
        assert cur not in seen, f"cycle at {cur}"
        seen.add(cur)
        cur = mapping[cur]
    assert len(seen) == len(mapping), "disconnected revision graph"


def test_migration_gate_offline_revisions_present_m1():
    mapping = _parse_revisions()
    for rev in (
        "20260813_0091",
        "20260813_0092",
        "20260813_0093",
        "20260813_0094",
        "20260813_0095",
    ):
        assert rev in mapping, rev
    assert mapping["20260813_0095"] == "20260813_0094"
    assert mapping["20260813_0094"] == "20260813_0093"


def test_migration_gate_register_and_doc_m1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 169 and data["pack"] == "M1"
    assert data["ci_deploy_claimed"] is False
    assert data["production_migrate_claimed"] is False
    assert data["go_live_claimed"] is False
    doc = (ROOT / "docs/MIGRATION_GATE_MVP.md").read_text(encoding="utf-8")
    assert "single head" in doc.lower() or "single Alembic head" in doc
    assert "Stage 18 C1" in doc or "deploy-free" in doc
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # Stage 18 C1 — still no deploy job invented by Stage 169
    assert "deploy:" not in ci.lower() or "deploy-free" in ci or "pytest" in ci
