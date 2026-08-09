"""Category-level tax rules (Stage 10 T1)

Revision ID: 20260809_0084
Revises: 20260809_0083
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0084"
down_revision = "20260809_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("product_categories") as batch:
        batch.add_column(
            sa.Column(
                "tax_rate_id",
                sa.String(length=36),
                sa.ForeignKey("tax_rates.id"),
                nullable=True,
            )
        )
        batch.create_index("ix_product_categories_tax_rate_id", ["tax_rate_id"])


def downgrade() -> None:
    with op.batch_alter_table("product_categories") as batch:
        batch.drop_index("ix_product_categories_tax_rate_id")
        batch.drop_column("tax_rate_id")
