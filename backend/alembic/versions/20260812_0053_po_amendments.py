"""purchase order amendment tracking

Revision ID: 20260812_0053
Revises: 20260812_0052
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0053"
down_revision = "20260812_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "purchase_order_amendments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_order_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_orders.id"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("notified_supplier", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("emailed_to", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_purchase_order_amendments_tenant_id",
        "purchase_order_amendments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_purchase_order_amendments_purchase_order_id",
        "purchase_order_amendments",
        ["purchase_order_id"],
    )
    op.create_index(
        "ix_purchase_order_amendments_po_revision",
        "purchase_order_amendments",
        ["purchase_order_id", "revision_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_order_amendments_po_revision", table_name="purchase_order_amendments")
    op.drop_index(
        "ix_purchase_order_amendments_purchase_order_id",
        table_name="purchase_order_amendments",
    )
    op.drop_index("ix_purchase_order_amendments_tenant_id", table_name="purchase_order_amendments")
    op.drop_table("purchase_order_amendments")
    op.drop_column("purchase_orders", "revision_no")
