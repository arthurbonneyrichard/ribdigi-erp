"""HRM: SSNIT-exempt and senior-staff flags, and when a payslip was emailed.

Revision ID: 20261114_0181
Revises: 20261114_0180
Create Date: 2026-11-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261114_0181"
down_revision = "20261114_0180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_employees") as batch:
        batch.add_column(sa.Column("ssnit_exempt", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("senior_staff", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.add_column(sa.Column("ssnit_exempt", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("senior_staff", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("emailed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hrm_payslips") as batch:
        for name in ("emailed_at", "senior_staff", "ssnit_exempt"):
            batch.drop_column(name)
    with op.batch_alter_table("hrm_employees") as batch:
        batch.drop_column("senior_staff")
        batch.drop_column("ssnit_exempt")
