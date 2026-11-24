"""Retail and wholesale package prices: Starter GHS 149, Professional GHS 599, Enterprise GHS 1,099 a month.

Adds the industry plans only where the code is missing, so a price the owner set by hand is kept.
An empty catalog is seeded by the app on first use.

Revision ID: 20261124_0236
Revises: 20261124_0235
Create Date: 2026-11-24
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "20261124_0236"
down_revision = "20261124_0235"
branch_labels = None
depends_on = None

PRICES = {
    "retail": ("149.00", "599.00", "1099.00"),
    "wholesale": ("149.00", "599.00", "1099.00"),
}


def upgrade() -> None:
    bind = op.get_bind()
    if "platform_billing_plans" not in sa.inspect(bind).get_table_names():
        return
    have = {row[0] for row in bind.execute(sa.text("SELECT code FROM platform_billing_plans"))}
    if not have:
        return
    plans = sa.table(
        "platform_billing_plans",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("package_code", sa.String),
        sa.column("industry", sa.String),
        sa.column("name", sa.String),
        sa.column("interval", sa.String),
        sa.column("amount", sa.Numeric),
        sa.column("currency", sa.String),
        sa.column("trial_days", sa.Integer),
        sa.column("grace_days", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = datetime.utcnow()
    rows = []
    for industry, prices in PRICES.items():
        for package_code, monthly in zip(("starter", "professional", "enterprise"), prices):
            for interval, amount in (("month", monthly), ("year", f"{float(monthly) * 10:.2f}")):
                code = f"{package_code}-{interval}-{industry}"
                if code in have:
                    continue
                word = "monthly" if interval == "month" else "yearly"
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "package_code": package_code,
                        "industry": industry,
                        "name": f"{package_code.title()} {word} ({industry.title()})",
                        "interval": interval,
                        "amount": amount,
                        "currency": "GHS",
                        "trial_days": 14,
                        "grace_days": 7,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
    if rows:
        op.bulk_insert(plans, rows)


def downgrade() -> None:
    bind = op.get_bind()
    if "platform_billing_plans" not in sa.inspect(bind).get_table_names():
        return
    for industry in PRICES:
        bind.execute(sa.text("DELETE FROM platform_billing_plans WHERE industry = :i"), {"i": industry})
