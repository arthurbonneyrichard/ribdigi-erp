"""HRM: junior-staff overtime tax and minimum wage on dated rates; overtime tax and warnings on payslips.

Revision ID: 20261113_0172
Revises: 20261113_0171
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0172"
down_revision = "20261113_0171"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_statutory_rates") as batch:
        batch.add_column(sa.Column("overtime_junior_cap", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("overtime_low_rate", sa.Numeric(6, 3), nullable=False, server_default="5"))
        batch.add_column(sa.Column("overtime_high_rate", sa.Numeric(6, 3), nullable=False, server_default="10"))
        batch.add_column(sa.Column("overtime_low_share_percent", sa.Numeric(6, 3), nullable=False, server_default="50"))
        batch.add_column(sa.Column("minimum_daily_wage", sa.Numeric(14, 2), nullable=True))
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.add_column(sa.Column("overtime_tax", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("warnings", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.drop_column("warnings")
        batch.drop_column("overtime_tax")
    with op.batch_alter_table("hrm_statutory_rates") as batch:
        for name in ("minimum_daily_wage", "overtime_low_share_percent", "overtime_high_rate", "overtime_low_rate", "overtime_junior_cap"):
            batch.drop_column(name)
