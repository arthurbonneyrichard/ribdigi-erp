"""API key usage statistics (Stage 7 K2)

Revision ID: 20260809_0082
Revises: 20260809_0081
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0082"
down_revision = "20260809_0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("api_keys") as batch:
        batch.add_column(
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0")
        )

    op.create_table(
        "api_key_usage_daily",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "api_key_id",
            sa.String(length=36),
            sa.ForeignKey("api_keys.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("usage_date", sa.String(length=10), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("api_key_id", "usage_date", name="uq_api_key_usage_daily_key_date"),
    )


def downgrade() -> None:
    op.drop_table("api_key_usage_daily")
    with op.batch_alter_table("api_keys") as batch:
        batch.drop_column("request_count")
