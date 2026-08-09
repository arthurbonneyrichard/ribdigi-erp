"""Add bank_branch on accounts for BR-10.3

Revision ID: 20260809_0065
Revises: 20260809_0064
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0065"
down_revision = "20260809_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(sa.Column("bank_branch", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("bank_branch")
