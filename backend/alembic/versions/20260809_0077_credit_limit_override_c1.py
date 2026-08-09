"""Credit-limit override fields on sales invoices (Stage 3 C1 / BR-11.1)

Revision ID: 20260809_0077
Revises: 20260809_0076
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0077"
down_revision = "20260809_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales_invoices") as batch:
        batch.add_column(
            sa.Column("credit_limit_overridden", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("credit_override_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("credit_override_by", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("credit_override_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sales_invoices") as batch:
        batch.drop_column("credit_override_at")
        batch.drop_column("credit_override_by")
        batch.drop_column("credit_override_reason")
        batch.drop_column("credit_limit_overridden")
