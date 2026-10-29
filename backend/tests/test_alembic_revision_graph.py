"""Alembic versions must form a unique linear chain (single head)."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _revisions() -> list[tuple[str, str, str | tuple[str, ...] | None]]:
    rows: list[tuple[str, str, str | tuple[str, ...] | None]] = []
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
                    parts: list[str] = []
                    for elt in val.elts:
                        if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                            raise AssertionError(f"{path.name}: merge down_revision must be revision ids")
                        parts.append(elt.value)
                    if len(parts) != 2:
                        raise AssertionError(f"{path.name}: merge must join exactly two revisions")
                    down = tuple(parts)
                else:
                    raise AssertionError(f"{path.name}: unsupported down_revision")
        assert rev, path.name
        rows.append((path.name, str(rev), down))
    return rows


def _parents(down: str | tuple[str, ...] | None) -> list[str]:
    if down is None:
        return []
    if isinstance(down, tuple):
        return list(down)
    return [down]


def test_revision_ids_unique():
    by_rev: dict[str, list[str]] = defaultdict(list)
    for name, rev, _down in _revisions():
        by_rev[rev].append(name)
    dupes = {k: v for k, v in by_rev.items() if len(v) > 1}
    assert not dupes, dupes


def test_single_head_linear_chain():
    rows = _revisions()
    ids = {rev for _n, rev, _d in rows}
    referenced: set[str] = set()
    merges: list[tuple[str, str, tuple[str, ...]]] = []
    for name, rev, down in rows:
        if isinstance(down, tuple):
            merges.append((name, rev, down))
        referenced.update(_parents(down))
    heads = ids - referenced
    # One head, 20261026_0149, after storefront media, the hybrid-schema relax,
    # restoring tables the live database skipped, till returns, and one open shift per cashier. The only join remains 20261008_0136, which merges the
    # offline-grant head 20261003_0134 with the restaurant/billing head
    # 20261008_0135.
    assert len(heads) == 1, heads
    assert heads == {"20261026_0149"}
    assert len(merges) == 1, merges
    _merge_name, merge_rev, merge_parents = merges[0]
    assert merge_rev == "20261008_0136"
    assert set(merge_parents) == {"20261003_0134", "20261008_0135"}
    assert any(rev == "20261011_0137" and down == "20261008_0136" for _n, rev, down in rows)
    assert any(rev == "20261011_0138" and down == "20261011_0137" for _n, rev, down in rows)
    assert any(rev == "20261021_0139" and down == "20261011_0138" for _n, rev, down in rows)
    assert any(rev == "20261021_0140" and down == "20261021_0139" for _n, rev, down in rows)
    assert any(rev == "20261021_0141" and down == "20261021_0140" for _n, rev, down in rows)
    assert any(rev == "20261022_0142" and down == "20261021_0141" for _n, rev, down in rows)
    assert any(rev == "20261022_0143" and down == "20261022_0142" for _n, rev, down in rows)
    assert any(rev == "20261023_0144" and down == "20261022_0143" for _n, rev, down in rows)
    assert any(rev == "20261023_0145" and down == "20261023_0144" for _n, rev, down in rows)
    assert any(rev == "20261026_0146" and down == "20261023_0145" for _n, rev, down in rows)
    assert any(rev == "20261026_0147" and down == "20261026_0146" for _n, rev, down in rows)
    assert any(rev == "20261026_0148" and down == "20261026_0147" for _n, rev, down in rows)
    assert any(rev == "20261026_0149" and down == "20261026_0148" for _n, rev, down in rows)
    children: dict[str | None, list[str]] = defaultdict(list)
    for _name, rev, down in rows:
        for parent in _parents(down):
            children[parent].append(rev)
    branched = {p: c for p, c in children.items() if len(c) > 1}
    assert set(branched) == {"20260920_0115"}, branched
    assert "20261001_0130" in ids
    assert any(rev == "20261001_0130" and down == "20260930_0129" for _n, rev, down in rows)
    assert "20261001_0131" in ids
    assert any(rev == "20261001_0131" and down == "20261001_0130" for _n, rev, down in rows)
    assert "20261001_0132" in ids
    assert any(rev == "20261001_0132" and down == "20261001_0131" for _n, rev, down in rows)
    assert "20261003_0133" in ids
    assert any(rev == "20261003_0133" and down == "20261001_0132" for _n, rev, down in rows)
