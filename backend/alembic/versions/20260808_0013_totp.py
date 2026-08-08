"""two-factor authentication fields

Revision ID: 20260808_0013
Revises: 20260808_0012
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0013"
down_revision = "20260808_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret_enc", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_pending_secret_enc", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("totp_confirmed_at", sa.DateTime(), nullable=True))

    op.create_table(
        "two_factor_backup_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_two_factor_backup_codes_tenant_id", "two_factor_backup_codes", ["tenant_id"])
    op.create_index("ix_two_factor_backup_codes_user_id", "two_factor_backup_codes", ["user_id"])
    op.create_index("ix_two_factor_backup_codes_code_hash", "two_factor_backup_codes", ["code_hash"])


def downgrade() -> None:
    op.drop_index("ix_two_factor_backup_codes_code_hash", table_name="two_factor_backup_codes")
    op.drop_index("ix_two_factor_backup_codes_user_id", table_name="two_factor_backup_codes")
    op.drop_index("ix_two_factor_backup_codes_tenant_id", table_name="two_factor_backup_codes")
    op.drop_table("two_factor_backup_codes")
    op.drop_column("users", "totp_confirmed_at")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_pending_secret_enc")
    op.drop_column("users", "totp_secret_enc")
