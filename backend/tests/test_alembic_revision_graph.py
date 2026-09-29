"""Alembic versions must form a unique linear chain (single head)."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revisions() -> list[tuple[str, str, str | None]]:
    rows: list[tuple[str, str, str | None]] = []
    for path in sorted(VERSIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rev = down = None
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            val = node.value
            if "revision" in names and isinstance(val, ast.Constant):
                rev = val.value
            if "down_revision" in names:
                if isinstance(val, ast.Constant):
                    down = val.value
                elif isinstance(val, ast.Tuple):
                    raise AssertionError(f"{path.name}: merge revisions are not allowed")
        assert rev, path.name
        rows.append((path.name, str(rev), None if down is None else str(down)))
    return rows


def test_revision_ids_unique():
    by_rev: dict[str, list[str]] = defaultdict(list)
    for name, rev, _down in _revisions():
        by_rev[rev].append(name)
    dupes = {k: v for k, v in by_rev.items() if len(v) > 1}
    assert not dupes, dupes


def test_single_head_linear_chain():
    rows = _revisions()
    ids = {rev for _n, rev, _d in rows}
    downs = {down for _n, _r, down in rows if down is not None}
    heads = ids - downs
    assert heads == {"20260928_0125"}, heads
    children: dict[str | None, list[str]] = defaultdict(list)
    for _name, rev, down in rows:
        children[down].append(rev)
    branched = {p: c for p, c in children.items() if len(c) > 1}
    assert not branched, branched
