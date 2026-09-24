"""Hotel module tables — rooms, guests, reservations.

Revision ID: 20260920_0109
Revises: 20260919_0108
Create Date: 2026-09-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0109"
down_revision = "20260919_0108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_rooms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("room_type", sa.String(length=40), nullable=False, server_default="standard"),
        sa.Column("floor", sa.String(length=40), nullable=True),
        sa.Column("max_occupancy", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("rate_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_hotel_rooms_tenant_code"),
    )
    op.create_index("ix_hotel_rooms_status", "hotel_rooms", ["status"])

    op.create_table(
        "hotel_guests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("id_document", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_hotel_guests_tenant_email"),
    )

    op.create_table(
        "hotel_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("reservation_number", sa.String(length=40), nullable=False, index=True),
        sa.Column("room_id", sa.String(length=36), sa.ForeignKey("hotel_rooms.id"), nullable=False, index=True),
        sa.Column("guest_id", sa.String(length=36), sa.ForeignKey("hotel_guests.id"), nullable=False, index=True),
        sa.Column("check_in_date", sa.Date(), nullable=False, index=True),
        sa.Column("check_out_date", sa.Date(), nullable=False, index=True),
        sa.Column("adults", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("children", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("nightly_rate", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hotel_reservations_status", "hotel_reservations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_hotel_reservations_status", table_name="hotel_reservations")
    op.drop_table("hotel_reservations")
    op.drop_table("hotel_guests")
    op.drop_index("ix_hotel_rooms_status", table_name="hotel_rooms")
    op.drop_table("hotel_rooms")
