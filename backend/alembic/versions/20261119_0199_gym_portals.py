"""Gym portals: member portal links, member feedback, trainer login link.

Revision ID: 20261119_0199
Revises: 20261119_0198
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0199"
down_revision = "20261119_0198"
branch_labels = None
depends_on = None


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.add_column("gym_trainers", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")))
    op.create_index("ix_gym_trainers_user_id", "gym_trainers", ["user_id"])
    op.create_table(
        "gym_portal_links", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"), _fk("member_id", "gym_members"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("last_used_at", sa.DateTime()),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_feedback", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"), _fk("member_id", "gym_members"),
        _fk("trainer_id", "gym_trainers", True),
        sa.Column("kind", sa.String(20), nullable=False, index=True), sa.Column("rating", sa.Integer()), sa.Column("message", sa.String(1000)),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("resolution", sa.String(500)), sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("gym_feedback")
    op.drop_table("gym_portal_links")
    op.drop_index("ix_gym_trainers_user_id", "gym_trainers")
    op.drop_column("gym_trainers", "user_id")
