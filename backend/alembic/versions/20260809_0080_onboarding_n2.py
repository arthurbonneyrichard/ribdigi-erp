"""Tenant onboarding checklist state (Stage 6 N2)

Revision ID: 20260809_0080
Revises: 20260809_0079
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0080"
down_revision = "20260809_0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("onboarding_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("onboarding_state")
