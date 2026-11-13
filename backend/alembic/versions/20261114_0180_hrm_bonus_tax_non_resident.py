"""HRM: GRA bonus tax (5% up to 15% of annual basic) and non-resident employees.

Revision ID: 20261114_0180
Revises: 20261113_0179
Create Date: 2026-11-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261114_0180"
down_revision = "20261113_0179"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.add_column(sa.Column("bonus_tax", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("bonus_concessional", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("bonus_relief_left", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("non_resident", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("hrm_employees") as batch:
        batch.add_column(sa.Column("non_resident", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("hrm_statutory_rates") as batch:
        batch.add_column(sa.Column("bonus_rate", sa.Numeric(6, 3), nullable=False, server_default="5"))
        batch.add_column(sa.Column("bonus_cap_percent", sa.Numeric(6, 3), nullable=False, server_default="15"))


def downgrade() -> None:
    with op.batch_alter_table("hrm_statutory_rates") as batch:
        batch.drop_column("bonus_cap_percent")
        batch.drop_column("bonus_rate")
    with op.batch_alter_table("hrm_employees") as batch:
        batch.drop_column("non_resident")
    with op.batch_alter_table("hrm_payslips") as batch:
        for name in ("non_resident", "bonus_relief_left", "bonus_concessional", "bonus_tax"):
            batch.drop_column(name)
