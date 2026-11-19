"""HRM vacancy approval: who decided and why, plus the company setting (off by default).

Revision ID: 20261119_0204h
Revises: 20261119_0203
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0204h"
down_revision = "20261119_0203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hrm_vacancies", sa.Column("decided_by", sa.String(36), nullable=True))
    op.add_column("hrm_vacancies", sa.Column("decision_note", sa.String(500), nullable=True))
    op.add_column("hrm_settings", sa.Column("vacancy_approval", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("hrm_settings", "vacancy_approval")
    op.drop_column("hrm_vacancies", "decision_note")
    op.drop_column("hrm_vacancies", "decided_by")
