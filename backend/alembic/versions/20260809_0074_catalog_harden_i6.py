"""Catalog harden: UoM conversion, brand logo, product weight/dimensions (I6)

Revision ID: 20260809_0074
Revises: 20260809_0073
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0074"
down_revision = "20260809_0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brands") as batch:
        batch.add_column(sa.Column("logo_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("units_of_measure") as batch:
        batch.add_column(
            sa.Column("base_unit_id", sa.String(length=36), sa.ForeignKey("units_of_measure.id"), nullable=True)
        )
        batch.add_column(
            sa.Column("conversion_factor", sa.Numeric(18, 6), nullable=False, server_default="1")
        )

    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("weight", sa.Numeric(14, 3), nullable=True))
        batch.add_column(sa.Column("length", sa.Numeric(14, 3), nullable=True))
        batch.add_column(sa.Column("width", sa.Numeric(14, 3), nullable=True))
        batch.add_column(sa.Column("height", sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("height")
        batch.drop_column("width")
        batch.drop_column("length")
        batch.drop_column("weight")
    with op.batch_alter_table("units_of_measure") as batch:
        batch.drop_column("conversion_factor")
        batch.drop_column("base_unit_id")
    with op.batch_alter_table("brands") as batch:
        batch.drop_column("logo_url")
