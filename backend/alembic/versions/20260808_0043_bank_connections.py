"""bank account API connections for live feed sync

Revision ID: 20260808_0043
Revises: 20260808_0042
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0043"
down_revision = "20260808_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_account_connections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="mock"),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("external_account_id", sa.String(length=120), nullable=True),
        sa.Column("feed_url", sa.String(length=500), nullable=True),
        sa.Column("credentials_enc", sa.Text(), nullable=True),
        sa.Column("auto_sync", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_match_after_sync", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_lookback_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_status", sa.String(length=30), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("last_statement_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_bank_connection_tenant_account"),
    )


def downgrade() -> None:
    op.drop_table("bank_account_connections")
