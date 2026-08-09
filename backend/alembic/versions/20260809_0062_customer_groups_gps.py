"""Customer groups and GPS coordinates on parties

Revision ID: 20260809_0062
Revises: 20260809_0061
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0062"
down_revision = "20260809_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_customer_groups_tenant_name"),
    )
    with op.batch_alter_table("parties") as batch:
        batch.add_column(
            sa.Column(
                "customer_group_id",
                sa.String(length=36),
                sa.ForeignKey("customer_groups.id"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("latitude", sa.Numeric(10, 7), nullable=True))
        batch.add_column(sa.Column("longitude", sa.Numeric(10, 7), nullable=True))
        batch.create_index("ix_parties_customer_group_id", ["customer_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("parties") as batch:
        batch.drop_index("ix_parties_customer_group_id")
        batch.drop_column("longitude")
        batch.drop_column("latitude")
        batch.drop_column("customer_group_id")
    op.drop_table("customer_groups")
