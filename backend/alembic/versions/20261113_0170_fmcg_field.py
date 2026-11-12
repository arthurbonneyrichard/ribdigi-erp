"""FMCG field work: territories (routes and reps) and outlet visits with phone GPS.

Revision ID: 20261113_0170
Revises: 20261113_0169
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0170"
down_revision = "20261113_0169"
branch_labels = None
depends_on = None


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


TABLES = {
    "fmcg_territories": lambda: [
        sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("daily_visit_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fmcg_territory_code"),
    ],
    "fmcg_territory_routes": lambda: [
        sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("territory_id", sa.String(36), sa.ForeignKey("fmcg_territories.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("fmcg_routes.id"), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "route_id", name="uq_fmcg_territory_route"),
    ],
    "fmcg_territory_reps": lambda: [
        sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("territory_id", sa.String(36), sa.ForeignKey("fmcg_territories.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.UniqueConstraint("territory_id", "user_id", name="uq_fmcg_territory_rep"),
    ],
    "fmcg_visits": lambda: [
        sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("outlet_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(36), nullable=True, index=True),
        sa.Column("territory_id", sa.String(36), nullable=True, index=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("in_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("in_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("in_accuracy_m", sa.Numeric(8, 1), nullable=True),
        sa.Column("distance_m", sa.Numeric(10, 1), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(), nullable=True),
        sa.Column("out_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("out_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("out_accuracy_m", sa.Numeric(8, 1), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("no_order_reason", sa.String(32), nullable=True),
        sa.Column("order_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("set_outlet_location", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("device", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    ],
}


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    for name, columns in TABLES.items():
        if name not in have:
            op.create_table(name, *columns())


def downgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    for name in reversed(list(TABLES)):
        if name in have:
            op.drop_table(name)
