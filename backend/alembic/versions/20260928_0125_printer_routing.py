"""Tenant printers, print agents, and print jobs.

Revision ID: 20260928_0125
Revises: 20260928_0124

Moved from colliding 20260928_0106, then from 0123 after coupon siblings took
0122–0124. Idempotent if printer objects already exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0125"
down_revision = "20260928_0124"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    cat_cols = _column_names("product_categories")
    if "prep_station" not in cat_cols:
        op.add_column(
            "product_categories",
            sa.Column("prep_station", sa.String(length=20), nullable=True),
        )
    prod_cols = _column_names("products")
    if "prep_station" not in prod_cols:
        op.add_column(
            "products",
            sa.Column("prep_station", sa.String(length=20), nullable=True),
        )

    tables = _table_names()
    if "print_agents" not in tables:
        op.create_table(
            "print_agents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=True),
            sa.Column("pairing_code_hash", sa.String(length=128), nullable=True),
            sa.Column("pairing_expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "ix_print_agents_tenant_id" not in _index_names("print_agents"):
        op.create_index("ix_print_agents_tenant_id", "print_agents", ["tenant_id"])
    if "ix_print_agents_store_id" not in _index_names("print_agents"):
        op.create_index("ix_print_agents_store_id", "print_agents", ["store_id"])
    if "ix_print_agents_token_hash" not in _index_names("print_agents"):
        op.create_index("ix_print_agents_token_hash", "print_agents", ["token_hash"])

    tables = _table_names()
    if "printers" not in tables:
        op.create_table(
            "printers",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("print_agents.id"), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("connection_type", sa.String(length=30), nullable=False, server_default="browser_dialog"),
            sa.Column("paper", sa.String(length=20), nullable=False, server_default="80mm"),
            sa.Column("purposes", sa.JSON(), nullable=True),
            sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("host", sa.String(length=255), nullable=True),
            sa.Column("port", sa.Integer(), nullable=False, server_default="9100"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "name"),
        )
    if "ix_printers_tenant_id" not in _index_names("printers"):
        op.create_index("ix_printers_tenant_id", "printers", ["tenant_id"])
    if "ix_printers_store_id" not in _index_names("printers"):
        op.create_index("ix_printers_store_id", "printers", ["store_id"])

    tables = _table_names()
    if "print_jobs" not in tables:
        op.create_table(
            "print_jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("printer_id", sa.String(length=36), sa.ForeignKey("printers.id"), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=True),
            sa.Column("purpose", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("idempotency_key", sa.String(length=180), nullable=False),
            sa.Column("reprint_of_job_id", sa.String(length=36), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("claimed_by_agent_id", sa.String(length=36), nullable=True),
            sa.Column("claimed_at", sa.DateTime(), nullable=True),
            sa.Column("printed_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "idempotency_key"),
        )
    if "ix_print_jobs_tenant_id" not in _index_names("print_jobs"):
        op.create_index("ix_print_jobs_tenant_id", "print_jobs", ["tenant_id"])
    if "ix_print_jobs_printer_id" not in _index_names("print_jobs"):
        op.create_index("ix_print_jobs_printer_id", "print_jobs", ["printer_id"])
    if "ix_print_jobs_source_id" not in _index_names("print_jobs"):
        op.create_index("ix_print_jobs_source_id", "print_jobs", ["source_id"])
    if "ix_print_jobs_status" not in _index_names("print_jobs"):
        op.create_index("ix_print_jobs_status", "print_jobs", ["status"])

    tables = _table_names()
    if "print_job_attempts" not in tables:
        op.create_table(
            "print_job_attempts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("job_id", sa.String(length=36), sa.ForeignKey("print_jobs.id"), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    if "ix_print_job_attempts_tenant_id" not in _index_names("print_job_attempts"):
        op.create_index("ix_print_job_attempts_tenant_id", "print_job_attempts", ["tenant_id"])
    if "ix_print_job_attempts_job_id" not in _index_names("print_job_attempts"):
        op.create_index("ix_print_job_attempts_job_id", "print_job_attempts", ["job_id"])


def downgrade() -> None:
    return
