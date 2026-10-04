"""UoM conversion ratios (BR-5.1).

Revision ID: 20260812_0073
Revises: 20260812_0072
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0073"
down_revision = "20260812_0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "units_of_measure",
        sa.Column("base_unit_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "units_of_measure",
        sa.Column(
            "conversion_ratio",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_foreign_key(
        "fk_units_of_measure_base_unit_id",
        "units_of_measure",
        "units_of_measure",
        ["base_unit_id"],
        ["id"],
    )
    op.create_index("ix_units_of_measure_base_unit_id", "units_of_measure", ["base_unit_id"])


def downgrade() -> None:
    op.drop_index("ix_units_of_measure_base_unit_id", table_name="units_of_measure")
    op.drop_constraint("fk_units_of_measure_base_unit_id", "units_of_measure", type_="foreignkey")
    op.drop_column("units_of_measure", "conversion_ratio")
    op.drop_column("units_of_measure", "base_unit_id")
