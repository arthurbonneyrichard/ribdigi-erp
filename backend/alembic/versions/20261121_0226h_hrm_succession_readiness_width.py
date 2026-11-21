"""HRM succession: readiness code 'one_two_years' is 13 characters, the column held 12 (failed on Postgres).

Revision ID: 20261121_0226h
Revises: 20261120_0225f
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261121_0226h"
down_revision = "20261120_0225f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_succession") as batch:
        batch.alter_column("readiness", existing_type=sa.String(12), type_=sa.String(20), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("hrm_succession") as batch:
        batch.alter_column("readiness", existing_type=sa.String(20), type_=sa.String(12), existing_nullable=False)
