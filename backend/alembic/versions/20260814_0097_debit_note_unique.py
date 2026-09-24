"""Unique debit_note_number per tenant on purchase_returns (BR-6.6).

Revision ID: 20260814_0097
Revises: 20260814_0096
Create Date: 2026-08-14
"""

from alembic import op


revision = "20260814_0097"
down_revision = "20260814_0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL treats NULLs as distinct, so draft returns (no DN yet) remain allowed.
    op.create_unique_constraint(
        "uq_purchase_returns_tenant_debit_note",
        "purchase_returns",
        ["tenant_id", "debit_note_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_purchase_returns_tenant_debit_note",
        "purchase_returns",
        type_="unique",
    )
