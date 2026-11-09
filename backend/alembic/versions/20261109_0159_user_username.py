"""Users get an optional username for the User sign-in, unique across the system.

Revision ID: 20261109_0159
Revises: 20261108_0158
Create Date: 2026-11-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261109_0159"
down_revision = "20261108_0158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.String(length=60), nullable=True))
        op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "username" in columns:
        op.drop_index("ix_users_username", table_name="users")
        op.drop_column("users", "username")
