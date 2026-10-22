"""Normalize stored tenant.industry aliases to canonical codes.

Revision ID: 20260928_0116
Revises: 20260920_0115

Maps known aliases (hospitality→hotel, supermarket→mart, …) without changing
unrecognized values. Never deletes tenants or business data.

Graph-only parent fix: this used to fork from 20260816_0105 while the linear
chain already continued 20260917_0105 … 20260920_0115. Upgrade SQL is unchanged.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0116"
down_revision = "20260920_0115"
branch_labels = None
depends_on = None

_ALIAS_SQL = [
    ("hospitality", "hotel"),
    ("hotels", "hotel"),
    ("lodging", "hotel"),
    ("accommodation", "hotel"),
    ("guest_house", "hotel"),
    ("guesthouse", "hotel"),
    ("retail_mart", "retail"),
    ("supermarket", "mart"),
    ("super_market", "mart"),
    ("grocery", "mart"),
    ("fast_moving_consumer_goods", "fmcg"),
    ("fmcg_distribution", "fmcg"),
    ("pharma", "pharmacy"),
    ("drugstore", "pharmacy"),
    ("resto", "restaurant"),
    ("food_service", "restaurant"),
    ("cafe", "restaurant"),
    ("wholesaler", "wholesale"),
    ("distributor", "distribution"),
    ("trading", "general_trading"),
    ("manufacture", "manufacturing"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for src, dest in _ALIAS_SQL:
        conn.execute(
            sa.text(
                "UPDATE tenants SET industry = :dest "
                "WHERE lower(trim(replace(replace(coalesce(industry, ''), '-', '_'), ' ', '_'))) = :src"
            ),
            {"dest": dest, "src": src},
        )
    conn.execute(
        sa.text(
            "UPDATE tenants SET industry = lower(trim(industry)) "
            "WHERE industry IS NOT NULL AND industry <> lower(trim(industry))"
        )
    )


def downgrade() -> None:
    pass
