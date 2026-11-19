"""Bakery regulars: birthday and text consent per phone number.

Revision ID: 20261119_0203
Revises: 20261119_0202
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0203"
down_revision = "20261119_0202"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bakery_regulars", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("phone", sa.String(40), nullable=False), sa.Column("name", sa.String(180)),
        sa.Column("birth_month", sa.Integer()), sa.Column("birth_day", sa.Integer()),
        sa.Column("texts_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_text_year", sa.Integer()), sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_bakery_regular_phone"),
    )


def downgrade() -> None:
    op.drop_table("bakery_regulars")
