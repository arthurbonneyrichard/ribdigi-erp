"""FMCG: proof of delivery, quality inspections, complaints.

Revision ID: 20261120_0216f
Revises: 20261120_0215f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0216f"
down_revision = "20261120_0215f"
branch_labels = None
depends_on = None


def _fk(name: str):
    return sa.ForeignKey(name)


def upgrade() -> None:
    op.create_table(
        "fmcg_proofs_of_delivery",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), _fk("fmcg_orders.id"), nullable=False, index=True),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("photo", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("accuracy_m", sa.Numeric(9, 1), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("captured_by", sa.String(36), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_id", name="uq_fmcg_pod_order"),
    )
    op.create_table(
        "fmcg_qc_inspections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("inspection_number", sa.String(40), nullable=False),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), _fk("product_batches.id"), nullable=True, index=True),
        sa.Column("supplier_id", sa.String(36), _fk("parties.id"), nullable=True, index=True),
        sa.Column("sample_size", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("packaging_ok", sa.Boolean(), nullable=True),
        sa.Column("label_ok", sa.Boolean(), nullable=True),
        sa.Column("expiry_ok", sa.Boolean(), nullable=True),
        sa.Column("temperature_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("certificate_ref", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("rejected_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("placed_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "inspection_number", name="uq_fmcg_qc_number"),
    )
    op.create_table(
        "fmcg_complaints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("complaint_number", sa.String(40), nullable=False),
        sa.Column("customer_id", sa.String(36), _fk("parties.id"), nullable=True, index=True),
        sa.Column("order_id", sa.String(36), _fk("fmcg_orders.id"), nullable=True, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=True, index=True),
        sa.Column("batch_id", sa.String(36), _fk("product_batches.id"), nullable=True, index=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "complaint_number", name="uq_fmcg_complaint_number"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_complaints")
    op.drop_table("fmcg_qc_inspections")
    op.drop_table("fmcg_proofs_of_delivery")
