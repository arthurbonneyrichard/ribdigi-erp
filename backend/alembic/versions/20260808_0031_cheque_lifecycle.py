"""cheque lifecycle clearing accounts

Revision ID: 20260808_0031
Revises: 20260808_0030
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0031"
down_revision = "20260808_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cheques",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("cheque_number", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("cheque_date", sa.DateTime(), nullable=True),
        sa.Column("party_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column(
            "customer_payment_id",
            sa.String(length=36),
            sa.ForeignKey("customer_payments.id"),
            nullable=True,
        ),
        sa.Column(
            "supplier_payment_id",
            sa.String(length=36),
            sa.ForeignKey("supplier_payments.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deposited_at", sa.DateTime(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        sa.Column("bounced_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "cheque_number", "direction", name="uq_cheques_tenant_num_dir"),
    )
    op.create_index("ix_cheques_tenant_id", "cheques", ["tenant_id"])
    op.create_index("ix_cheques_direction", "cheques", ["direction"])
    op.create_index("ix_cheques_status", "cheques", ["status"])
    op.create_index("ix_cheques_cheque_number", "cheques", ["cheque_number"])
    op.create_index("ix_cheques_party_id", "cheques", ["party_id"])
    op.create_index("ix_cheques_customer_payment_id", "cheques", ["customer_payment_id"])
    op.create_index("ix_cheques_supplier_payment_id", "cheques", ["supplier_payment_id"])


def downgrade() -> None:
    op.drop_table("cheques")
