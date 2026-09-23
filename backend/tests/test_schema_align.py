"""Non-destructive schema align for hybrid live Postgres vs production ORM."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.schema_align import align_async_engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_align_is_idempotent_on_full_orm_schema(db_engine):
    await align_async_engine(db_engine)
    await align_async_engine(db_engine)


@pytest.mark.asyncio
async def test_align_adds_dropped_product_description(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(text("ALTER TABLE products DROP COLUMN description"))
        cols = await conn.execute(text("PRAGMA table_info(products)"))
        names = {row[1] for row in cols}
        assert "description" not in names
    await align_async_engine(db_engine)
    async with db_engine.begin() as conn:
        cols = await conn.execute(text("PRAGMA table_info(products)"))
        names = {row[1] for row in cols}
    assert "description" in names


@pytest.mark.asyncio
async def test_align_copies_plan_code_into_empty_package_code(db_engine, db_session, seeded):
    async with db_engine.begin() as conn:
        await conn.execute(text("ALTER TABLE tenants ADD COLUMN plan_code VARCHAR(40) DEFAULT 'trial'"))
        await conn.execute(
            text("UPDATE tenants SET package_code = 'trial', plan_code = 'starter' WHERE slug = 'alpha'")
        )
    await align_async_engine(db_engine)
    async with db_engine.begin() as conn:
        row = (
            await conn.execute(text("SELECT package_code, plan_code FROM tenants WHERE slug = 'alpha'"))
        ).first()
    assert row is not None
    assert row[0] == "starter"
    assert row[1] == "starter"


def test_bootstrap_calls_schema_align():
    text_src = (ROOT / "backend/scripts/bootstrap.py").read_text(encoding="utf-8")
    assert "align_async_engine" in text_src
    assert "schema align complete" in text_src
