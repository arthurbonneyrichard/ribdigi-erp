"""HRM time: shifts, roster, work sites with QR, clock events, clock corrections, overtime.

Revision ID: 20261113_0168
Revises: 20261113_0167
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0168"
down_revision = "20261113_0167"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _employee():
    return sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True)


TABLES = {
    "hrm_shifts": lambda: [
        _id(), _tenant(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("starts_at", sa.String(5), nullable=False),
        sa.Column("ends_at", sa.String(5), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    ],
    "hrm_roster": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("day", sa.Date(), nullable=False, index=True),
        sa.Column("shift_id", sa.String(36), sa.ForeignKey("hrm_shifts.id"), nullable=False, index=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.UniqueConstraint("employee_id", "day", name="uq_hrm_roster_day"),
    ],
    "hrm_sites": lambda: [
        _id(), _tenant(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("radius_m", sa.Integer(), nullable=False, server_default="150"),
        sa.Column("qr_secret", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    ],
    "hrm_clock_events": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False, index=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("accuracy_m", sa.Numeric(8, 1), nullable=True),
        sa.Column("distance_m", sa.Numeric(10, 1), nullable=True),
        sa.Column("device", sa.String(160), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("voided", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("external_ref", sa.String(80), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "external_ref", name="uq_hrm_clock_external"),
    ],
    "hrm_biometric_links": lambda: [
        _id(), _tenant(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=True),
        sa.Column("username", sa.String(120), nullable=True),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("device_serial", sa.String(64), nullable=True),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_result", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("device_serial", name="uq_hrm_biometric_serial"),
    ],
    "hrm_clock_corrections": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("in_at", sa.DateTime(), nullable=True),
        sa.Column("out_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("decision_note", sa.String(255), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    ],
    "hrm_overtime": lambda: [
        _id(), _tenant(), _employee(),
        sa.Column("period", sa.String(7), nullable=False, index=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(14, 4), nullable=False),
        sa.Column("rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="approved", index=True),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("employee_id", "period", name="uq_hrm_overtime_month"),
    ],
}

ADD = {
    "hrm_settings": [
        ("hours_per_day", sa.Numeric(5, 2), "8"),
        ("overtime_rate", sa.Numeric(5, 2), "1.5"),
        ("clock_needs_site", sa.Boolean(), sa.false()),
    ],
    "hrm_payslips": [("overtime", sa.Numeric(14, 2), "0")],
    "hrm_employees": [("biometric_id", sa.String(32), None)],
}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    have = set(insp.get_table_names())
    for name, columns in TABLES.items():
        if name not in have:
            op.create_table(name, *columns())
    for table, cols in ADD.items():
        if table not in have:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, kind, default in cols:
            if name not in existing:
                op.add_column(table, sa.Column(name, kind, nullable=True, server_default=default))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    have = set(insp.get_table_names())
    for table, cols in ADD.items():
        if table not in have:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, _kind, _default in cols:
            if name in existing:
                op.drop_column(table, name)
    for name in reversed(list(TABLES)):
        if name in have:
            op.drop_table(name)
