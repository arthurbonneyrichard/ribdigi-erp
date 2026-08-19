"""ADR-490 phase 17 — company print templates + header/footer.

Revision ID: 20260814_0100
Revises: 20260814_0099
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0100"
down_revision = "20260814_0099"
branch_labels = None
depends_on = None

PRINT_COLS = (
    ("invoice_print_template", sa.String(length=20), "a4"),
    ("receipt_print_template", sa.String(length=20), "thermal_80"),
    ("document_header", sa.Text(), None),
    ("document_footer", sa.Text(), None),
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "companies" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    for name, col_type, server_default in PRINT_COLS:
        if name in cols:
            continue
        kwargs: dict = {"nullable": True if server_default is None else False}
        if server_default is not None:
            kwargs["server_default"] = server_default
        op.add_column("companies", sa.Column(name, col_type, **kwargs))

    # Backfill from tenant legacy print settings.
    op.execute(
        sa.text(
            "UPDATE companies SET "
            "invoice_print_template = COALESCE("
            "(SELECT t.invoice_print_template FROM tenants t WHERE t.id = companies.tenant_id), "
            "'a4'), "
            "receipt_print_template = COALESCE("
            "(SELECT t.receipt_print_template FROM tenants t WHERE t.id = companies.tenant_id), "
            "'thermal_80'), "
            "document_header = COALESCE("
            "companies.document_header, "
            "(SELECT t.document_header FROM tenants t WHERE t.id = companies.tenant_id)), "
            "document_footer = COALESCE("
            "companies.document_footer, "
            "(SELECT t.document_footer FROM tenants t WHERE t.id = companies.tenant_id))"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "companies" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("companies")}
    for name, _, _ in PRINT_COLS:
        if name in cols:
            op.drop_column("companies", name)
