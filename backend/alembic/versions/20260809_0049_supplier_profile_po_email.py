"""Supplier/party profile fields, contacts, PO email timestamps

Revision ID: 20260809_0049
Revises: 20260809_0048
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0049"
down_revision = "20260809_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parties", sa.Column("code", sa.String(length=40), nullable=True))
    op.add_column("parties", sa.Column("party_type", sa.String(length=40), nullable=True))
    op.add_column("parties", sa.Column("category", sa.String(length=80), nullable=True))
    op.add_column(
        "parties",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("parties", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("parties", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "parties",
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("parties", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("parties", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE parties SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE parties SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    op.create_index("ix_parties_code", "parties", ["code"])
    op.create_index("ix_parties_status", "parties", ["status"])
    op.create_unique_constraint("uq_parties_tenant_kind_code", "parties", ["tenant_id", "kind", "code"])

    op.create_table(
        "party_contacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("party_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("designation", sa.String(length=80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_party_contacts_tenant_id", "party_contacts", ["tenant_id"])
    op.create_index("ix_party_contacts_party_id", "party_contacts", ["party_id"])

    op.add_column("purchase_orders", sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.add_column("purchase_orders", sa.Column("emailed_to", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "emailed_to")
    op.drop_column("purchase_orders", "sent_at")
    op.drop_table("party_contacts")
    op.drop_constraint("uq_parties_tenant_kind_code", "parties", type_="unique")
    op.drop_index("ix_parties_status", table_name="parties")
    op.drop_index("ix_parties_code", table_name="parties")
    op.drop_column("parties", "updated_at")
    op.drop_column("parties", "created_at")
    op.drop_column("parties", "payment_terms_days")
    op.drop_column("parties", "notes")
    op.drop_column("parties", "address")
    op.drop_column("parties", "status")
    op.drop_column("parties", "category")
    op.drop_column("parties", "party_type")
    op.drop_column("parties", "code")
