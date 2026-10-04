"""Tenant onboarding checklist state (BR first-run setup).

Revision ID: 20260812_0066
Revises: 20260812_0065
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0066"
down_revision = "20260812_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("onboarding_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("onboarding_state")
