"""Delete revoked platform staff arthurbonneyrichard@outlook.com.

Revision ID: 20260920_0115
Revises: 20260920_0114
Create Date: 2026-09-20

Ops request: dashboard access already revoked; permanently remove the account
from the platform workspace (and related auth/MFA/prefs rows).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0115"
down_revision = "20260920_0114"
branch_labels = None
depends_on = None

_TARGET_EMAIL = "arthurbonneyrichard@outlook.com"


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :name
            LIMIT 1
            """
        ),
        {"name": name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # Resolve target user ids on the platform workspace (or matching email anywhere
    # on platform tenant ids / slugs).
    if dialect == "sqlite":
        user_rows = conn.execute(
            sa.text(
                """
                SELECT u.id
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(:email)
                  AND (
                    t.slug IN ('platform', 'ribdigi-platform')
                    OR t.id IN ('platform', 'ribdigi-platform')
                    OR lower(t.company_name) = lower('Ribdigi House')
                  )
                """
            ),
            {"email": _TARGET_EMAIL},
        ).fetchall()
    else:
        user_rows = conn.execute(
            sa.text(
                """
                SELECT u.id
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(:email)
                  AND (
                    t.slug IN ('platform', 'ribdigi-platform')
                    OR t.id IN ('platform', 'ribdigi-platform')
                    OR lower(t.company_name) = lower('Ribdigi House')
                  )
                """
            ),
            {"email": _TARGET_EMAIL},
        ).fetchall()

    user_ids = [r[0] for r in user_rows]
    if not user_ids:
        return

    child_tables = [
        "auth_sessions",
        "auth_tokens",
        "webauthn_credentials",
        "webauthn_challenges",
        "two_factor_backup_codes",
        "user_store_memberships",
        "notification_preferences",
    ]
    for table in child_tables:
        if dialect != "sqlite" and not _table_exists(conn, table):
            continue
        for uid in user_ids:
            conn.execute(
                sa.text(f"DELETE FROM {table} WHERE user_id = :uid"),
                {"uid": uid},
            )

    # Null optional FKs (best-effort; skip missing tables).
    null_updates = [
        ("notifications", "user_id"),
        ("pos_devices", "user_id"),
        ("branches", "manager_id"),
        ("departments", "head_user_id"),
        ("stores", "manager_id"),
        ("warehouses", "manager_id"),
    ]
    for table, col in null_updates:
        if dialect != "sqlite" and not _table_exists(conn, table):
            continue
        for uid in user_ids:
            conn.execute(
                sa.text(f"UPDATE {table} SET {col} = NULL WHERE {col} = :uid"),
                {"uid": uid},
            )

    for uid in user_ids:
        conn.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": uid})


def downgrade() -> None:
    # Irreversible ops delete — no restore.
    pass
