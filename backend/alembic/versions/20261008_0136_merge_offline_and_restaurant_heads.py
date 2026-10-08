"""Merge offline-grant and restaurant billing Alembic heads.

Revision ID: 20261008_0136
Revises: 20261003_0134, 20261008_0135
Create Date: 2026-10-08

`20261003_0134` and `20261008_0135` both descend from `20260920_0115`.
This empty revision is the single head so `alembic upgrade head` can run.
"""

revision = "20261008_0136"
down_revision = ("20261003_0134", "20261008_0135")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
