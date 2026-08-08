"""live FX feed columns on exchange_rates

Revision ID: 20260808_0039
Revises: 20260808_0038
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0039"
down_revision = "20260808_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exchange_rates",
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
    )
    op.add_column(
        "exchange_rates",
        sa.Column("provider_fetched_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("fx_auto_refresh", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("tenants", "fx_auto_refresh")
    op.drop_column("exchange_rates", "provider_fetched_at")
    op.drop_column("exchange_rates", "source")
