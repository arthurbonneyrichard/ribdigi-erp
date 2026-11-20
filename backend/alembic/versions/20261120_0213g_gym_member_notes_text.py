"""Gym members: notes column is Text, as the model says.

Revision ID: 20261120_0213g
Revises: 20261119_0212g
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0213g"
down_revision = "20261119_0212g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("gym_members", "notes", existing_type=sa.String(), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # Longer notes would not fit a VARCHAR(500); cut them to the old limit rather than fail.
    op.execute("UPDATE gym_members SET notes = LEFT(notes, 500) WHERE notes IS NOT NULL AND LENGTH(notes) > 500")
    op.alter_column("gym_members", "notes", existing_type=sa.Text(), type_=sa.String(500), existing_nullable=True)
