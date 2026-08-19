"""Recurring expense skip/modify + notify-before fields

Revision ID: 20260809_0064
Revises: 20260809_0063
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0064"
down_revision = "20260809_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch:
        batch.add_column(sa.Column("skip_next", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("next_amount", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("next_description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_notified_for", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch:
        batch.drop_column("last_notified_for")
        batch.drop_column("next_description")
        batch.drop_column("next_amount")
        batch.drop_column("skip_next")
