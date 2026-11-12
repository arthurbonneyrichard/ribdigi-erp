"""Restaurant and bakery till sales rung offline carry a one-time key so they book once.

Revision ID: 20261112_0162
Revises: 20261112_0161
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261112_0162"
down_revision = "20261112_0161"
branch_labels = None
depends_on = None


TABLES = (
    ("restaurant_orders", "uq_restaurant_order_offline_ref"),
    ("bakery_sales", "uq_bakery_sale_offline_ref"),
)


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for table, constraint in TABLES:
        if table not in insp.get_table_names():
            continue
        columns = {c["name"] for c in insp.get_columns(table)}
        if "offline_ref" not in columns:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("offline_ref", sa.String(64), nullable=True))
                batch.create_unique_constraint(constraint, ["tenant_id", "offline_ref"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for table, constraint in TABLES:
        if table not in insp.get_table_names():
            continue
        columns = {c["name"] for c in insp.get_columns(table)}
        if "offline_ref" in columns:
            with op.batch_alter_table(table) as batch:
                batch.drop_constraint(constraint, type_="unique")
                batch.drop_column("offline_ref")
