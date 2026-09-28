"""Hotel PMS ops: rate plans, requests, cashier, night audit.

Revision ID: 20260928_0119
Revises: 20260928_0118
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0119"
down_revision = "20260928_0118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hotel_guests", sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("hotel_guests", sa.Column("travel_agent", sa.String(length=150), nullable=True))
    op.add_column("hotel_guests", sa.Column("loyalty_tier", sa.String(length=40), nullable=True))
    op.add_column("hotel_settings", sa.Column("property_name", sa.String(length=150), nullable=True))
    op.add_column("hotel_reservations", sa.Column("rate_plan_id", sa.String(length=36), nullable=True))
    op.add_column(
        "hotel_reservations",
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
    )
    op.add_column("hotel_reservations", sa.Column("discount_authorized_by", sa.String(length=36), nullable=True))
    op.add_column("hotel_housekeeping_tasks", sa.Column("due_at", sa.DateTime(), nullable=True))

    op.create_table(
        "hotel_rate_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("room_type", sa.String(length=40), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("weekday_only", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("weekend_only", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("min_nights", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_table(
        "hotel_guest_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("reservation_id", sa.String(length=36), sa.ForeignKey("hotel_reservations.id"), nullable=True),
        sa.Column("room_id", sa.String(length=36), sa.ForeignKey("hotel_rooms.id"), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False, server_default="service"),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "hotel_lost_found",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("room_id", sa.String(length=36), sa.ForeignKey("hotel_rooms.id"), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="lost"),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "hotel_cashier_shifts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("opened_by", sa.String(length=36), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("opening_float", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("closed_by", sa.String(length=36), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closing_float", sa.Numeric(14, 2), nullable=True),
        sa.Column("payments_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
    )
    op.create_table(
        "hotel_night_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "business_date"),
    )


def downgrade() -> None:
    op.drop_table("hotel_night_audits")
    op.drop_table("hotel_cashier_shifts")
    op.drop_table("hotel_lost_found")
    op.drop_table("hotel_guest_requests")
    op.drop_table("hotel_rate_plans")
    op.drop_column("hotel_housekeeping_tasks", "due_at")
    op.drop_column("hotel_reservations", "discount_authorized_by")
    op.drop_column("hotel_reservations", "discount_percent")
    op.drop_column("hotel_reservations", "rate_plan_id")
    op.drop_column("hotel_settings", "property_name")
    op.drop_column("hotel_guests", "loyalty_tier")
    op.drop_column("hotel_guests", "travel_agent")
    op.drop_column("hotel_guests", "consent_marketing")
