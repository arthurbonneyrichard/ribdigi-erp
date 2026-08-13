"""Add party profile fields (code, type, category, status, address, GPS).

Revision ID: 20260813_0080
Revises: 20260813_0079
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0080"
down_revision = "20260813_0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parties", sa.Column("code", sa.String(length=64), nullable=True))
    op.add_column(
        "parties",
        sa.Column("profile_type", sa.String(length=32), nullable=False, server_default="registered"),
    )
    op.add_column("parties", sa.Column("category", sa.String(length=80), nullable=True))
    op.add_column(
        "parties",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("parties", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("latitude", sa.Numeric(10, 7), nullable=True))
    op.add_column("parties", sa.Column("longitude", sa.Numeric(10, 7), nullable=True))
    op.create_index(
        "uq_parties_tenant_code",
        "parties",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_parties_tenant_code", table_name="parties")
    op.drop_column("parties", "longitude")
    op.drop_column("parties", "latitude")
    op.drop_column("parties", "address")
    op.drop_column("parties", "status")
    op.drop_column("parties", "category")
    op.drop_column("parties", "profile_type")
    op.drop_column("parties", "code")
