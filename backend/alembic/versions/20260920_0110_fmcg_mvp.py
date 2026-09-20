"""FMCG module tables — trade schemes, routes, route stops.

Revision ID: 20260920_0110
Revises: 20260920_0109
Create Date: 2026-09-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0110"
down_revision = "20260920_0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_trade_schemes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("scheme_type", sa.String(length=20), nullable=False, server_default="percent"),
        sa.Column("value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("buy_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("get_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fmcg_trade_schemes_tenant_code"),
    )

    op.create_table(
        "fmcg_routes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("driver_name", sa.String(length=150), nullable=True),
        sa.Column("vehicle", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fmcg_routes_tenant_code"),
    )

    op.create_table(
        "fmcg_route_stops",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("fmcg_routes.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("visit_day", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "route_id",
            "customer_id",
            name="uq_fmcg_route_stops_tenant_route_customer",
        ),
    )


def downgrade() -> None:
    op.drop_table("fmcg_route_stops")
    op.drop_table("fmcg_routes")
    op.drop_table("fmcg_trade_schemes")
