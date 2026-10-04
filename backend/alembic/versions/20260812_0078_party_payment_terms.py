"""Party payment_terms_days for AR/AP due dates (BR-6.1).

Revision ID: 20260812_0078
Revises: 20260812_0077
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0078"
down_revision = "20260812_0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parties",
        sa.Column(
            "payment_terms_days",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )


def downgrade() -> None:
    op.drop_column("parties", "payment_terms_days")
