"""Webhook delivery retry scheduling (Stage 7 W2)

Revision ID: 20260809_0081
Revises: 20260809_0080
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0081"
down_revision = "20260809_0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("webhook_deliveries") as batch:
        batch.add_column(sa.Column("next_retry_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_webhook_deliveries_next_retry_at", ["next_retry_at"])


def downgrade() -> None:
    with op.batch_alter_table("webhook_deliveries") as batch:
        batch.drop_index("ix_webhook_deliveries_next_retry_at")
        batch.drop_column("next_retry_at")
