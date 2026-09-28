"""Hotel events and banquets.

Revision ID: 20260928_0121
Revises: 20260928_0120
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0121"
down_revision = "20260928_0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("space_name", sa.String(length=120), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False, index=True),
        sa.Column("ends_on", sa.Date(), nullable=False, index=True),
        sa.Column("expected_guests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="inquiry", index=True),
        sa.Column("room_id", sa.String(length=36), sa.ForeignKey("hotel_rooms.id"), nullable=True, index=True),
        sa.Column("guest_id", sa.String(length=36), sa.ForeignKey("hotel_guests.id"), nullable=True, index=True),
        sa.Column("deposit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("hotel_events")
