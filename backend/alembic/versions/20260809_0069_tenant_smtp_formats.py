"""Tenant SMTP overrides and regional format settings

Revision ID: 20260809_0069
Revises: 20260809_0068
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0069"
down_revision = "20260809_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("date_format", sa.String(length=20), nullable=False, server_default="DD/MM/YYYY"))
        batch.add_column(sa.Column("number_format", sa.String(length=20), nullable=False, server_default="1,234.56"))
        batch.add_column(sa.Column("time_format", sa.String(length=20), nullable=False, server_default="24h"))
        batch.add_column(sa.Column("smtp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("smtp_host", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_port", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("smtp_username", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_password_enc", sa.Text(), nullable=True))
        batch.add_column(sa.Column("smtp_from_email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_from_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.text("1")))
        batch.add_column(sa.Column("smtp_use_ssl", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("smtp_use_ssl")
        batch.drop_column("smtp_use_tls")
        batch.drop_column("smtp_from_name")
        batch.drop_column("smtp_from_email")
        batch.drop_column("smtp_password_enc")
        batch.drop_column("smtp_username")
        batch.drop_column("smtp_port")
        batch.drop_column("smtp_host")
        batch.drop_column("smtp_enabled")
        batch.drop_column("time_format")
        batch.drop_column("number_format")
        batch.drop_column("date_format")
