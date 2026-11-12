"""HRM: reporting managers, two-step leave approval, leave that builds up and carries over.

Revision ID: 20261113_0165
Revises: 20261113_0164
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0165"
down_revision = "20261113_0164"
branch_labels = None
depends_on = None

ADD = {
    "hrm_settings": [
        ("leave_accrual", sa.String(16), "upfront"),
        ("carry_over_days", sa.Integer(), "0"),
    ],
    "hrm_employees": [("manager_id", sa.String(36), None)],
    "hrm_leave_requests": [
        ("stage", sa.String(16), "hr"),
        ("manager_decided_by", sa.String(36), None),
        ("manager_decided_at", sa.DateTime(), None),
        ("manager_note", sa.String(255), None),
    ],
}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, cols in ADD.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, kind, default in cols:
            if name not in have:
                op.add_column(table, sa.Column(name, kind, nullable=True, server_default=default))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, cols in ADD.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, _kind, _default in cols:
            if name in have:
                op.drop_column(table, name)
