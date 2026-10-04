"""Hotel + FMCG completion R3 — settings, groups, reports, scheme apply, dispatch.

Revision ID: 20260920_0112
Revises: 20260920_0111
Create Date: 2026-09-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0112"
down_revision = "20260920_0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, unique=True, index=True),
        sa.Column("check_in_time", sa.String(length=8), nullable=False, server_default="14:00"),
        sa.Column("check_out_time", sa.String(length=8), nullable=False, server_default="11:00"),
        sa.Column("cancellation_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("no_show_fee_percent", sa.Numeric(7, 4), nullable=False, server_default="100"),
        sa.Column("early_checkin_fee", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("late_checkout_fee", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("service_charge_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "hotel_reservation_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("group_number", sa.String(length=40), nullable=False, index=True),
        sa.Column("guest_id", sa.String(length=36), sa.ForeignKey("hotel_guests.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=150), nullable=True),
        sa.Column("booking_source", sa.String(length=40), nullable=False, server_default="corporate"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "group_number", name="uq_hotel_reservation_groups_tenant_number"),
    )

    op.add_column(
        "hotel_reservations",
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("hotel_reservation_groups.id"), nullable=True),
    )
    op.create_index("ix_hotel_reservations_group_id", "hotel_reservations", ["group_id"])

    op.create_table(
        "fmcg_dispatches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("fmcg_routes.id"), nullable=False, index=True),
        sa.Column("dispatch_number", sa.String(length=40), nullable=False, index=True),
        sa.Column("dispatch_date", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("driver_name", sa.String(length=150), nullable=True),
        sa.Column("vehicle", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "dispatch_number", name="uq_fmcg_dispatches_tenant_number"),
    )

    op.create_table(
        "fmcg_customer_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("fmcg_routes.id"), nullable=True, index=True),
        sa.Column("salesperson_name", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "customer_id", name="uq_fmcg_customer_assignments_tenant_customer"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_customer_assignments")
    op.drop_table("fmcg_dispatches")
    op.drop_index("ix_hotel_reservations_group_id", table_name="hotel_reservations")
    op.drop_column("hotel_reservations", "group_id")
    op.drop_table("hotel_reservation_groups")
    op.drop_table("hotel_settings")
