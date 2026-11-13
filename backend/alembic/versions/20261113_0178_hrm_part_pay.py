"""HRM weekly / fortnightly part-payments on a monthly payroll.

Revision ID: 20261113_0178
Revises: 20261113_0177
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0178"
down_revision = "20261113_0177"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_employees") as batch:
        batch.add_column(sa.Column("pay_frequency", sa.String(16), nullable=False, server_default="monthly"))
    with op.batch_alter_table("hrm_settings") as batch:
        batch.add_column(sa.Column("part_pay_percent", sa.Numeric(6, 2), nullable=False, server_default="80"))
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.add_column(sa.Column("part_paid", sa.Numeric(14, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.drop_column("part_paid")
    with op.batch_alter_table("hrm_settings") as batch:
        batch.drop_column("part_pay_percent")
    with op.batch_alter_table("hrm_employees") as batch:
        batch.drop_column("pay_frequency")
