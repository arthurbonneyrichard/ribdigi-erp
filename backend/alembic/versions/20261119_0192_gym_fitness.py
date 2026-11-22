"""Gym fitness: exercise library, workout programmes, workout logs, body measurements.

Revision ID: 20261119_0192
Revises: 20261119_0191
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0192"
down_revision = "20261119_0191"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_exercises", _id(), _tenant(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("muscle_group", sa.String(80)), sa.Column("equipment", sa.String(120)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_gym_exercise_name"),
    )
    op.create_table(
        "gym_programmes", _id(), _tenant(), _fk("member_id", "gym_members"), _fk("trainer_id", "gym_trainers", True),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("goal", sa.String(300)),
        sa.Column("starts_on", sa.Date(), nullable=False), sa.Column("ends_on", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_programme_lines", _id(), _tenant(), _fk("programme_id", "gym_programmes"), _fk("exercise_id", "gym_exercises"),
        sa.Column("day_of_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sets", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("weight_kg", sa.Numeric(8, 2)), sa.Column("rest_seconds", sa.Integer()), sa.Column("notes", sa.String(300)),
    )
    op.create_table(
        "gym_workout_logs", _id(), _tenant(), _fk("programme_id", "gym_programmes"), _fk("line_id", "gym_programme_lines"),
        _fk("member_id", "gym_members"),
        sa.Column("done_on", sa.Date(), nullable=False, index=True),
        sa.Column("sets_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reps_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight_kg", sa.Numeric(8, 2)), sa.Column("recorded_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_measurements", _id(), _tenant(), _fk("member_id", "gym_members"),
        sa.Column("measured_on", sa.Date(), nullable=False, index=True),
        sa.Column("weight_kg", sa.Numeric(6, 2)), sa.Column("height_cm", sa.Numeric(6, 1)),
        sa.Column("body_fat_pct", sa.Numeric(5, 1)), sa.Column("waist_cm", sa.Numeric(6, 1)),
        sa.Column("chest_cm", sa.Numeric(6, 1)), sa.Column("hips_cm", sa.Numeric(6, 1)),
        sa.Column("arms_cm", sa.Numeric(6, 1)), sa.Column("thighs_cm", sa.Numeric(6, 1)),
        sa.Column("resting_hr", sa.Integer()), sa.Column("notes", sa.String(500)),
        sa.Column("recorded_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    for t in ("gym_measurements", "gym_workout_logs", "gym_programme_lines", "gym_programmes", "gym_exercises"):
        op.drop_table(t)
