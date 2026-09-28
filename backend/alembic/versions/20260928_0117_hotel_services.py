"""Hotel billable services catalog (folio extras).

Revision ID: 20260928_0117
Revises: 20260928_0116
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0117"
down_revision = "20260928_0116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hotel_services",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="extra"),
        sa.Column("unit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hotel_services_tenant_id", "hotel_services", ["tenant_id"])
    op.create_index("ix_hotel_services_category", "hotel_services", ["category"])
    op.create_unique_constraint("uq_hotel_services_tenant_code", "hotel_services", ["tenant_id", "code"])


def downgrade() -> None:
    op.drop_table("hotel_services")
