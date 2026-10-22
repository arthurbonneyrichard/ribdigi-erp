"""Pharmacy Rx lifecycle extras after 0130.

Revision ID: 20261001_0131
Revises: 20261001_0130

Partial-fill qty, pharmacist approve audit fields, lot holds, and Rx attachments.
Does not invent HIS clinics. 0130 (dosage/rx_only/prescriptions) remains required.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261001_0131"
down_revision = "20261001_0130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "prescriptions" in tables:
        cols = {c["name"] for c in insp.get_columns("prescriptions")}
        if "approved_by" not in cols:
            op.add_column("prescriptions", sa.Column("approved_by", sa.String(length=36), nullable=True))
        if "approved_at" not in cols:
            op.add_column("prescriptions", sa.Column("approved_at", sa.DateTime(), nullable=True))
        if "dispensed_at" not in cols:
            op.add_column("prescriptions", sa.Column("dispensed_at", sa.DateTime(), nullable=True))

    if "prescription_items" in tables:
        cols = {c["name"] for c in insp.get_columns("prescription_items")}
        if "qty_dispensed" not in cols:
            op.add_column(
                "prescription_items",
                sa.Column("qty_dispensed", sa.Numeric(14, 3), nullable=False, server_default="0"),
            )

    if "batch_holds" not in tables:
        op.create_table(
            "batch_holds",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(length=36),
                sa.ForeignKey("tenants.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "batch_id",
                sa.String(length=36),
                sa.ForeignKey("product_batches.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("hold_type", sa.String(length=20), nullable=False, server_default="quarantine"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("released_at", sa.DateTime(), nullable=True),
        )
    if "batch_holds" in set(sa.inspect(bind).get_table_names()):
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_batch_holds_tenant_batch "
            "ON batch_holds (tenant_id, batch_id)"
        )

    if "prescription_attachments" not in tables:
        op.create_table(
            "prescription_attachments",
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
            sa.Column("storage_key", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=80), nullable=True),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "prescription_attachments" in tables:
        op.drop_table("prescription_attachments")
    if "batch_holds" in tables:
        op.execute("DROP INDEX IF EXISTS uq_batch_holds_tenant_batch")
        op.drop_table("batch_holds")
    if "prescription_items" in tables:
        cols = {c["name"] for c in insp.get_columns("prescription_items")}
        if "qty_dispensed" in cols:
            op.drop_column("prescription_items", "qty_dispensed")
    if "prescriptions" in tables:
        cols = {c["name"] for c in insp.get_columns("prescriptions")}
        if "dispensed_at" in cols:
            op.drop_column("prescriptions", "dispensed_at")
        if "approved_at" in cols:
            op.drop_column("prescriptions", "approved_at")
        if "approved_by" in cols:
            op.drop_column("prescriptions", "approved_by")
