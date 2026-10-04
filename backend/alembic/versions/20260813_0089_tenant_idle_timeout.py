"""Add tenant inactivity timeout minutes (BR-19.3).

Revision ID: 20260813_0089
Revises: 20260813_0088
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0089"
down_revision = "20260813_0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "inactivity_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "inactivity_timeout_minutes")
