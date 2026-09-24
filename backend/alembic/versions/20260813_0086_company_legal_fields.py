"""Add company legal/contact/address fields on tenants (BR-2.1 / BR-20.1).

Revision ID: 20260813_0086
Revises: 20260813_0085
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0086"
down_revision = "20260813_0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("legal_name", sa.String(length=200), nullable=True))
    op.add_column("tenants", sa.Column("registration_number", sa.String(length=80), nullable=True))
    op.add_column("tenants", sa.Column("contact_person", sa.String(length=150), nullable=True))
    op.add_column("tenants", sa.Column("billing_address", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("shipping_address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "shipping_address")
    op.drop_column("tenants", "billing_address")
    op.drop_column("tenants", "contact_person")
    op.drop_column("tenants", "registration_number")
    op.drop_column("tenants", "legal_name")
