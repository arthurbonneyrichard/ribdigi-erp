"""COA hierarchy + system flag for Stage 3 A2 (BR-10.1)

Revision ID: 20260809_0075
Revises: 20260809_0074
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0075"
down_revision = "20260809_0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(
            sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True)
        )
        batch.add_column(
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.create_index("ix_accounts_parent_id", ["parent_id"])
        batch.create_unique_constraint("uq_accounts_tenant_code", ["tenant_id", "code"])
    # Mark known seeded system codes (idempotent for existing tenants)
    accounts = sa.table(
        "accounts",
        sa.column("code", sa.String),
        sa.column("is_system", sa.Boolean),
    )
    op.execute(
        accounts.update()
        .where(
            accounts.c.code.in_(
                [
                    "1000",
                    "1010",
                    "1020",
                    "1100",
                    "1200",
                    "1300",
                    "2000",
                    "2015",
                    "2100",
                    "3000",
                    "3900",
                    "4000",
                    "4100",
                    "4200",
                    "4300",
                    "5000",
                    "6000",
                ]
            )
        )
        .values(is_system=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_constraint("uq_accounts_tenant_code", type_="unique")
        batch.drop_index("ix_accounts_parent_id")
        batch.drop_column("is_active")
        batch.drop_column("is_system")
        batch.drop_column("parent_id")
