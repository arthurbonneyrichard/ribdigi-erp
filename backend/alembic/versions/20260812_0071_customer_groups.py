"""Customer groups + party.customer_group_id (BR-7.1).

Revision ID: 20260812_0071
Revises: 20260812_0070
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0071"
down_revision = "20260812_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_customer_groups_tenant_code"),
    )
    op.create_index("ix_customer_groups_tenant_id", "customer_groups", ["tenant_id"])
    op.add_column(
        "parties",
        sa.Column("customer_group_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_parties_customer_group_id",
        "parties",
        "customer_groups",
        ["customer_group_id"],
        ["id"],
    )
    op.create_index("ix_parties_customer_group_id", "parties", ["customer_group_id"])


def downgrade() -> None:
    op.drop_index("ix_parties_customer_group_id", table_name="parties")
    op.drop_constraint("fk_parties_customer_group_id", "parties", type_="foreignkey")
    op.drop_column("parties", "customer_group_id")
    op.drop_index("ix_customer_groups_tenant_id", table_name="customer_groups")
    op.drop_table("customer_groups")
