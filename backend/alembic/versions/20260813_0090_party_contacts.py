"""Add party_contacts for multi-contact profiles (BR-6.1).

Revision ID: 20260813_0090
Revises: 20260813_0089
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0090"
down_revision = "20260813_0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "party_contacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("party_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("designation", sa.String(length=120), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_party_contacts_tenant_party", "party_contacts", ["tenant_id", "party_id"])


def downgrade() -> None:
    op.drop_index("ix_party_contacts_tenant_party", table_name="party_contacts")
    op.drop_table("party_contacts")
