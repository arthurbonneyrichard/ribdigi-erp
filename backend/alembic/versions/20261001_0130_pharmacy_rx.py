"""Pharmacy catalog dosage/rx_only plus simple prescription records.

Revision ID: 20261001_0130
Revises: 20260930_0129

Product-level dosage instructions and an Rx-only flag, plus a tenant-scoped
prescription header/lines table optionally linked to a sales invoice.
No HIS, clinics, dispensing, or pharmacist-license workflow.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261001_0130"
down_revision = "20260930_0129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "products" in tables:
        cols = {c["name"] for c in insp.get_columns("products")}
        if "dosage_instructions" not in cols:
            op.add_column("products", sa.Column("dosage_instructions", sa.Text(), nullable=True))
        if "rx_only" not in cols:
            op.add_column(
                "products",
                sa.Column("rx_only", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    if "prescriptions" not in tables:
        op.create_table(
            "prescriptions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(length=36),
                sa.ForeignKey("tenants.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("rx_number", sa.String(length=50), nullable=False, index=True),
            sa.Column(
                "customer_id",
                sa.String(length=36),
                sa.ForeignKey("parties.id"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "sale_id",
                sa.String(length=36),
                sa.ForeignKey("sales_invoices.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("prescriber_name", sa.String(length=150), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="recorded"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "rx_number", name="uq_prescriptions_tenant_rx_number"),
        )

    if "prescription_items" not in tables:
        op.create_table(
            "prescription_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(length=36),
                sa.ForeignKey("tenants.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "prescription_id",
                sa.String(length=36),
                sa.ForeignKey("prescriptions.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "product_id",
                sa.String(length=36),
                sa.ForeignKey("products.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "variant_id",
                sa.String(length=36),
                sa.ForeignKey("product_variants.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
            sa.Column("dosage_text", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "prescription_items" in tables:
        op.drop_table("prescription_items")
    if "prescriptions" in tables:
        op.drop_table("prescriptions")
    if "products" in tables:
        cols = {c["name"] for c in insp.get_columns("products")}
        if "rx_only" in cols:
            op.drop_column("products", "rx_only")
        if "dosage_instructions" in cols:
            op.drop_column("products", "dosage_instructions")
