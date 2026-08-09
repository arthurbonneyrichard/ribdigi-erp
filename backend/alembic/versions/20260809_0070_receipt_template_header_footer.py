"""Receipt print template + document header/footer (BR-20.4 / E14)

Revision ID: 20260809_0070
Revises: 20260809_0069
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0070"
down_revision = "20260809_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column(
                "receipt_print_template",
                sa.String(length=20),
                nullable=False,
                server_default="thermal_80",
            )
        )
        batch.add_column(sa.Column("document_header", sa.Text(), nullable=True))
        batch.add_column(sa.Column("document_footer", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("document_footer")
        batch.drop_column("document_header")
        batch.drop_column("receipt_print_template")
