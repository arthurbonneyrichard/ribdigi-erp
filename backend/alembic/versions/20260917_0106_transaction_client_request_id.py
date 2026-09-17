"""Add client_request_id for POS sale idempotency (offline sync).

Revision ID: 20260917_0106
Revises: 20260917_0105
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260917_0106"
down_revision = "20260917_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_transactions_client_request_id",
        "transactions",
        ["client_request_id"],
    )
    # Partial unique: only when client_request_id is set (Postgres).
    # SQLite tests use create_all from models UniqueConstraint.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX uq_transactions_tenant_client_request
            ON transactions (tenant_id, client_request_id)
            WHERE client_request_id IS NOT NULL
            """
        )
    else:
        op.create_unique_constraint(
            "uq_transactions_tenant_client_request",
            "transactions",
            ["tenant_id", "client_request_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_transactions_tenant_client_request")
    else:
        op.drop_constraint(
            "uq_transactions_tenant_client_request",
            "transactions",
            type_="unique",
        )
    op.drop_index("ix_transactions_client_request_id", table_name="transactions")
    op.drop_column("transactions", "client_request_id")
