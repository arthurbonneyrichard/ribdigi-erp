"""Stage 164 — sync_queue_items, sync_conflicts, transactions.client_request_id.

Revision ID: 20260813_0092
Revises: 20260813_0091
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0092"
down_revision = "20260813_0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("client_request_id", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_transactions_client_request_id", "transactions", ["client_request_id"]
    )
    op.create_unique_constraint(
        "uq_transactions_tenant_client_request_id",
        "transactions",
        ["tenant_id", "client_request_id"],
    )

    op.create_table(
        "sync_queue_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "device_id",
            sa.String(length=36),
            sa.ForeignKey("offline_devices.id"),
            nullable=True,
        ),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("op_type", sa.String(length=40), nullable=False),
        sa.Column("client_op_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result_entity_id", sa.String(length=36), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("acked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "client_op_id"),
    )
    op.create_index("ix_sync_queue_items_tenant_id", "sync_queue_items", ["tenant_id"])
    op.create_index("ix_sync_queue_items_device_id", "sync_queue_items", ["device_id"])
    op.create_index("ix_sync_queue_items_direction", "sync_queue_items", ["direction"])
    op.create_index("ix_sync_queue_items_op_type", "sync_queue_items", ["op_type"])
    op.create_index("ix_sync_queue_items_client_op_id", "sync_queue_items", ["client_op_id"])
    op.create_index("ix_sync_queue_items_status", "sync_queue_items", ["status"])

    op.create_table(
        "sync_conflicts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "queue_item_id",
            sa.String(length=36),
            sa.ForeignKey("sync_queue_items.id"),
            nullable=True,
        ),
        sa.Column(
            "device_id",
            sa.String(length=36),
            sa.ForeignKey("offline_devices.id"),
            nullable=True,
        ),
        sa.Column("op_type", sa.String(length=40), nullable=False),
        sa.Column("client_op_id", sa.String(length=80), nullable=True),
        sa.Column("client_payload", sa.JSON(), nullable=False),
        sa.Column("server_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sync_conflicts_tenant_id", "sync_conflicts", ["tenant_id"])
    op.create_index("ix_sync_conflicts_queue_item_id", "sync_conflicts", ["queue_item_id"])
    op.create_index("ix_sync_conflicts_device_id", "sync_conflicts", ["device_id"])
    op.create_index("ix_sync_conflicts_op_type", "sync_conflicts", ["op_type"])
    op.create_index("ix_sync_conflicts_client_op_id", "sync_conflicts", ["client_op_id"])
    op.create_index("ix_sync_conflicts_status", "sync_conflicts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sync_conflicts_status", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_client_op_id", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_op_type", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_device_id", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_queue_item_id", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_tenant_id", table_name="sync_conflicts")
    op.drop_table("sync_conflicts")

    op.drop_index("ix_sync_queue_items_status", table_name="sync_queue_items")
    op.drop_index("ix_sync_queue_items_client_op_id", table_name="sync_queue_items")
    op.drop_index("ix_sync_queue_items_op_type", table_name="sync_queue_items")
    op.drop_index("ix_sync_queue_items_direction", table_name="sync_queue_items")
    op.drop_index("ix_sync_queue_items_device_id", table_name="sync_queue_items")
    op.drop_index("ix_sync_queue_items_tenant_id", table_name="sync_queue_items")
    op.drop_table("sync_queue_items")

    op.drop_constraint(
        "uq_transactions_tenant_client_request_id", "transactions", type_="unique"
    )
    op.drop_index("ix_transactions_client_request_id", table_name="transactions")
    op.drop_column("transactions", "client_request_id")
