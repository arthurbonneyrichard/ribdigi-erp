"""Sales invoice email metadata and default print template

Revision ID: 20260809_0059
Revises: 20260809_0058
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0059"
down_revision = "20260809_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales_invoices") as batch:
        batch.add_column(sa.Column("emailed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("emailed_to", sa.String(length=255), nullable=True))
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column("invoice_print_template", sa.String(length=20), nullable=False, server_default="a4")
        )


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("invoice_print_template")
    with op.batch_alter_table("sales_invoices") as batch:
        batch.drop_column("emailed_to")
        batch.drop_column("emailed_at")
