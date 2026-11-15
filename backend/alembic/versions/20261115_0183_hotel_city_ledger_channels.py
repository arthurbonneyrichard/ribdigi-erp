"""Hotel: city ledger (bill a stay to a company) and iCal channel feeds per room.

Revision ID: 20261115_0183
Revises: 20261115_0186
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_0183"
down_revision = "20261115_0186"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hotel_reservations") as batch:
        batch.add_column(sa.Column("bill_to_party_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=True))
        batch.add_column(sa.Column("channel_feed_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("channel_uid", sa.String(255), nullable=True))
    op.create_index("ix_hotel_reservations_bill_to_party_id", "hotel_reservations", ["bill_to_party_id"])
    op.create_index("ix_hotel_reservations_channel_feed_id", "hotel_reservations", ["channel_feed_id"])
    op.create_table(
        "hotel_channel_feeds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("hotel_rooms.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False, server_default="other"),
        sa.Column("import_url", sa.String(1000), nullable=True),
        sa.Column("export_token", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("export_token", name="uq_hotel_channel_feeds_export_token"),
    )
    op.create_index("ix_hotel_channel_feeds_tenant_id", "hotel_channel_feeds", ["tenant_id"])
    op.create_index("ix_hotel_channel_feeds_room_id", "hotel_channel_feeds", ["room_id"])


def downgrade() -> None:
    op.drop_index("ix_hotel_channel_feeds_room_id", table_name="hotel_channel_feeds")
    op.drop_index("ix_hotel_channel_feeds_tenant_id", table_name="hotel_channel_feeds")
    op.drop_table("hotel_channel_feeds")
    op.drop_index("ix_hotel_reservations_channel_feed_id", table_name="hotel_reservations")
    op.drop_index("ix_hotel_reservations_bill_to_party_id", table_name="hotel_reservations")
    with op.batch_alter_table("hotel_reservations") as batch:
        batch.drop_column("channel_uid")
        batch.drop_column("channel_feed_id")
        batch.drop_column("bill_to_party_id")
