"""Purchase order amendment tracking

Revision ID: 20260809_0051
Revises: 20260809_0050
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0051"
down_revision = "20260809_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
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
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.String(length=36), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "purchase_order_id", "revision"),
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


def downgrade() -> None:
    op.drop_table("purchase_order_amendments")
    op.drop_column("purchase_orders", "revision")
