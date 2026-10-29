"""Hotel online booking link.

Revision ID: 20261026_0148
Revises: 20261026_0147
Create Date: 2026-10-26

A hotel can record an existing website or a new domain. Guests request a
stay on that link. The host row does not verify DNS. A request is a
tentative reservation and does not take a payment. Skipped when the table
exists. Do not apply this to live ribdigi_erp from this change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261026_0148"
down_revision = "20261026_0147"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "hotel_booking_links"):
        return
    op.create_table(
        "hotel_booking_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("link_kind", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", name="uq_hotel_booking_link_tenant"),
        sa.UniqueConstraint("hostname", name="uq_hotel_booking_link_hostname"),
    )
    op.create_index("ix_hotel_booking_links_tenant_id", "hotel_booking_links", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "hotel_booking_links"):
        return
    op.drop_index("ix_hotel_booking_links_tenant_id", table_name="hotel_booking_links")
    op.drop_table("hotel_booking_links")
