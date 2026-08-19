"""Stage 1 D12 — user↔store assignment deferred (ADR-005)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_adr_005_defers_user_store_membership():
    adr = (ROOT / "docs" / "ADR_005_USER_STORE_ASSIGNMENT.md").read_text(encoding="utf-8")
    assert "No `users.store_id`" in adr or "No users.store_id" in adr.replace("`", "")
    assert "stores.manager_id" in adr

    models = (ROOT / "backend" / "app" / "models.py").read_text(encoding="utf-8")
    # User model must not gain store_id in Stage 1; Store keeps manager_id
    user_block = models.split("class User(Base):", 1)[1].split("class ", 1)[0]
    assert "store_id" not in user_block
    store_block = models.split("class Store(Base):", 1)[1].split("class ", 1)[0]
    assert "manager_id" in store_block
