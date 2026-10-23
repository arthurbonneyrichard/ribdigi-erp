"""One open till shift per cashier.

Revision ID: 20261023_0145
Revises: 20261023_0144
Create Date: 2026-10-23

The till page and the page frame both open the signed-in cashier's shift at
start-up. When the two requests landed together, each created a shift, and the
"current shift" lookup then failed with MultipleResultsFound (HTTP 500 on
GET /pos/sessions/current). A live database had three empty shifts for one
cashier opened within 60 ms.

This closes any extra open shift that has no sales (keeping each cashier's
newest), then adds a partial unique index so a cashier can have at most one
open shift. Duplicates that already have sales are left open and the index is
skipped, so nothing with money on it is touched; the service lookup tolerates
duplicates either way.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261023_0145"
down_revision = "20261023_0144"
branch_labels = None
depends_on = None

INDEX = "uq_pos_sessions_one_open_per_user"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE pos_sessions SET status = 'closed', closed_at = CURRENT_TIMESTAMP,
                   actual_cash = expected_cash, variance = 0,
                   notes = 'Closed automatically: duplicate empty shift opened at the same moment'
            WHERE status = 'open' AND COALESCE(sale_count, 0) = 0 AND id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, user_id ORDER BY opened_at DESC, id DESC
                    ) AS rn
                    FROM pos_sessions WHERE status = 'open'
                ) ranked WHERE rn > 1
            )
            """
        )
    )
    still_duplicated = bind.execute(
        sa.text(
            "SELECT 1 FROM pos_sessions WHERE status = 'open' "
            "GROUP BY tenant_id, user_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes("pos_sessions")}
    if still_duplicated is None and INDEX not in existing:
        op.create_index(
            INDEX,
            "pos_sessions",
            ["tenant_id", "user_id"],
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
            sqlite_where=sa.text("status = 'open'"),
        )


def downgrade() -> None:
    existing = {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes("pos_sessions")}
    if INDEX in existing:
        op.drop_index(INDEX, table_name="pos_sessions")
