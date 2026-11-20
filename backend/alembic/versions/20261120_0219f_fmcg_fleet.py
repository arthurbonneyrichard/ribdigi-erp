"""FMCG fleet: vehicles, vehicle logs, dispatch vehicle link.

Revision ID: 20261120_0219f
Revises: 20261120_0218f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0219f"
down_revision = "20261120_0218f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("plate", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False, server_default="van"),
        sa.Column("make_model", sa.String(120), nullable=True),
        sa.Column("driver_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="active", index=True),
        sa.Column("odometer_km", sa.Numeric(12, 1), nullable=False, server_default="0"),
        sa.Column("insurance_expiry", sa.Date(), nullable=True),
        sa.Column("roadworthy_expiry", sa.Date(), nullable=True),
        sa.Column("licence_expiry", sa.Date(), nullable=True),
        sa.Column("service_every_km", sa.Numeric(12, 1), nullable=True),
        sa.Column("last_service_km", sa.Numeric(12, 1), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "plate", name="uq_fmcg_vehicle_plate"),
    )
    op.add_column("fmcg_dispatches", sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("fmcg_vehicles.id"), nullable=True))
    op.create_index("ix_fmcg_dispatches_vehicle_id", "fmcg_dispatches", ["vehicle_id"])
    op.create_table(
        "fmcg_vehicle_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("fmcg_vehicles.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(12), nullable=False, index=True),
        sa.Column("log_date", sa.Date(), nullable=False, index=True),
        sa.Column("odometer_km", sa.Numeric(12, 1), nullable=True),
        sa.Column("litres", sa.Numeric(10, 2), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("vendor", sa.String(120), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("dispatch_id", sa.String(36), sa.ForeignKey("fmcg_dispatches.id"), nullable=True, index=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fmcg_vehicle_logs")
    op.drop_index("ix_fmcg_dispatches_vehicle_id", table_name="fmcg_dispatches")
    op.drop_column("fmcg_dispatches", "vehicle_id")
    op.drop_table("fmcg_vehicles")
