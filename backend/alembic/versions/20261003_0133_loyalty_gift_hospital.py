"""Loyalty points, gift cards, hospital visits, and checkout payment notices.

Revision ID: 20261003_0133
Revises: 20261001_0132

Gift cards and loyalty are tenant stored value. Hospital visits are a patient
desk, not a diagnosis or insurance module. Checkout notices record payment
information only — they do not capture card funds or invent subscription revenue.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261003_0133"
down_revision = "20261001_0132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "parties" in tables:
        cols = {c["name"] for c in insp.get_columns("parties")}
        if "loyalty_points" not in cols:
            op.add_column(
                "parties",
                sa.Column("loyalty_points", sa.Numeric(14, 2), nullable=False, server_default="0"),
            )

    if "gift_cards" not in tables:
        op.create_table(
            "gift_cards",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("issued_to_party_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_gift_cards_tenant_code"),
        )
        op.create_index("ix_gift_cards_tenant_id", "gift_cards", ["tenant_id"])
        op.create_index("ix_gift_cards_code", "gift_cards", ["code"])

    if "hospital_patients" not in tables:
        op.create_table(
            "hospital_patients",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_hospital_patients_tenant_id", "hospital_patients", ["tenant_id"])

    if "hospital_encounters" not in tables:
        op.create_table(
            "hospital_encounters",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("patient_id", sa.String(length=36), sa.ForeignKey("hospital_patients.id"), nullable=False),
            sa.Column("reason", sa.String(length=240), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_hospital_encounters_tenant_id", "hospital_encounters", ["tenant_id"])
        op.create_index("ix_hospital_encounters_patient_id", "hospital_encounters", ["patient_id"])

    if "checkout_payment_notices" not in tables:
        op.create_table(
            "checkout_payment_notices",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("method", sa.String(length=40), nullable=False),
            sa.Column("reference", sa.String(length=100), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("funds_captured", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_checkout_payment_notices_tenant_id", "checkout_payment_notices", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "checkout_payment_notices" in tables:
        op.drop_table("checkout_payment_notices")
    if "hospital_encounters" in tables:
        op.drop_table("hospital_encounters")
    if "hospital_patients" in tables:
        op.drop_table("hospital_patients")
    if "gift_cards" in tables:
        op.drop_table("gift_cards")
    if "parties" in tables:
        cols = {c["name"] for c in insp.get_columns("parties")}
        if "loyalty_points" in cols:
            op.drop_column("parties", "loyalty_points")
