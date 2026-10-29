"""Restaurant online booking link and guest requests.

Revision ID: 20261026_0146
Revises: 20261023_0145
Create Date: 2026-10-26

A restaurant can record an existing website or a new domain and take guest
booking requests on that link. The host row does not verify DNS. A booking
is not an order and does not take a payment. Skipped when the tables exist.
Do not apply this to live ribdigi_erp from this change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261026_0146"
down_revision = "20261023_0145"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "restaurant_booking_links"):
        op.create_table(
            "restaurant_booking_links",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("hostname", sa.String(length=253), nullable=False),
            sa.Column("link_kind", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", name="uq_restaurant_booking_link_tenant"),
            sa.UniqueConstraint("hostname", name="uq_restaurant_booking_link_hostname"),
        )
        op.create_index("ix_restaurant_booking_links_tenant_id", "restaurant_booking_links", ["tenant_id"])
    if not _has_table(bind, "restaurant_bookings"):
        op.create_table(
            "restaurant_bookings",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("booking_number", sa.String(length=40), nullable=False),
            sa.Column("guest_name", sa.String(length=180), nullable=False),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("party_size", sa.Integer(), nullable=False),
            sa.Column("booked_for", sa.DateTime(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "booking_number", name="uq_restaurant_booking_number"),
        )
        op.create_index("ix_restaurant_bookings_tenant_id", "restaurant_bookings", ["tenant_id"])
        op.create_index("ix_restaurant_bookings_booked_for", "restaurant_bookings", ["booked_for"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "restaurant_bookings"):
        op.drop_index("ix_restaurant_bookings_booked_for", table_name="restaurant_bookings")
        op.drop_index("ix_restaurant_bookings_tenant_id", table_name="restaurant_bookings")
        op.drop_table("restaurant_bookings")
    if _has_table(bind, "restaurant_booking_links"):
        op.drop_index("ix_restaurant_booking_links_tenant_id", table_name="restaurant_booking_links")
        op.drop_table("restaurant_booking_links")
