"""Gym and HRM desks, each on its own tables.

Revision ID: 20261106_0157
Revises: 20261106_0156
Create Date: 2026-11-06

Skipped when the tables exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_0157"
down_revision = "20261106_0156"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("gym_plans"):
        return
    op.create_table(
        "gym_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visit_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "gym_members",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("member_number", sa.String(length=40), nullable=False),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True, index=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("emergency_contact", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.String(length=None), nullable=True),
        sa.Column("joined_on", sa.Date(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "member_number", name="uq_gym_member_number"),
    )
    op.create_table(
        "gym_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("membership_number", sa.String(length=40), nullable=False),
        sa.Column("member_id", sa.String(length=36), sa.ForeignKey("gym_members.id"), nullable=False, index=True),
        sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("gym_plans.id"), nullable=False, index=True),
        sa.Column("starts_on", sa.Date(), nullable=False, index=True),
        sa.Column("ends_on", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("frozen_on", sa.Date(), nullable=True),
        sa.Column("visits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_renewal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("refunded", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("refund_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "membership_number", name="uq_gym_membership_number"),
    )
    op.create_table(
        "gym_till_shifts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("opening_cash", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("counted_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("opened_by", sa.String(length=36), nullable=True),
        sa.Column("closed_by", sa.String(length=36), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "gym_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("shift_id", sa.String(length=36), sa.ForeignKey("gym_till_shifts.id"), nullable=False, index=True),
        sa.Column("membership_id", sa.String(length=36), sa.ForeignKey("gym_memberships.id"), nullable=True, index=True),
        sa.Column("member_id", sa.String(length=36), sa.ForeignKey("gym_members.id"), nullable=True, index=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )
    op.create_table(
        "gym_check_ins",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("member_id", sa.String(length=36), sa.ForeignKey("gym_members.id"), nullable=False, index=True),
        sa.Column("membership_id", sa.String(length=36), sa.ForeignKey("gym_memberships.id"), nullable=True, index=True),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("refused_reason", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=False, index=True),
    )
    op.create_table(
        "gym_classes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("trainer_name", sa.String(length=150), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "gym_class_bookings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("class_id", sa.String(length=36), sa.ForeignKey("gym_classes.id"), nullable=False, index=True),
        sa.Column("member_id", sa.String(length=36), sa.ForeignKey("gym_members.id"), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "hrm_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("annual_leave_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("working_days_per_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ssnit_employee_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_employer_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("paye_bands", sa.JSON(), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_hrm_settings_tenant"),
    )
    op.create_table(
        "hrm_employees",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_number", sa.String(length=40), nullable=False),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True, index=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("hired_on", sa.Date(), nullable=False),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("left_reason", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("basic_salary", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("allowances", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_number", sa.String(length=40), nullable=True),
        sa.Column("tin", sa.String(length=40), nullable=True),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("bank_account", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "employee_number", name="uq_hrm_employee_number"),
    )
    op.create_table(
        "hrm_leave_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("leave_type", sa.String(length=20), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False, index=True),
        sa.Column("ends_on", sa.Date(), nullable=False, index=True),
        sa.Column("days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("reason", sa.String(length=None), nullable=True),
        sa.Column("decision_note", sa.String(length=255), nullable=True),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "hrm_attendance",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("day", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("marked_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("tenant_id", "employee_id", "day", name="uq_hrm_attendance_day"),
    )
    op.create_table(
        "hrm_payroll_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("run_number", sa.String(length=40), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        sa.Column("gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paye", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_employee", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_employer", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("staff_paid_at", sa.DateTime(), nullable=True),
        sa.Column("paye_paid_at", sa.DateTime(), nullable=True),
        sa.Column("ssnit_paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "period", name="uq_hrm_payroll_period"),
    )
    op.create_table(
        "hrm_payslips",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("hrm_payroll_runs.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(length=36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("basic", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("allowances", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("bonus", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("unpaid_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unpaid_deduction", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_employee", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paye", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ssnit_employer", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "hrm_payslips",
        "hrm_payroll_runs",
        "hrm_attendance",
        "hrm_leave_requests",
        "hrm_employees",
        "hrm_settings",
        "gym_class_bookings",
        "gym_classes",
        "gym_check_ins",
        "gym_payments",
        "gym_till_shifts",
        "gym_memberships",
        "gym_members",
        "gym_plans",
    ):
        if _has_table(table):
            op.drop_table(table)
