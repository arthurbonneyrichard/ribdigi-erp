"""Bootstrap database schema via Alembic, with create_all fallback (non-production only)."""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path

from app.config import settings
from app.db import engine
from app.models import Base

_MIG_0106 = Path(__file__).resolve().parents[1] / "alembic" / "versions" / (
    "20260917_0106_transaction_client_request_id.py"
)
_MIG_0107 = Path(__file__).resolve().parents[1] / "alembic" / "versions" / (
    "20260917_0107_pos_devices.py"
)
_BUILD_ID = Path("/app/.build-id")
_REQUIRED_MARKERS = (
    "RIBDIGI_0106_IF_NOT_EXISTS_V3",
    "ADD COLUMN IF NOT EXISTS client_request_id",
)
_FORBIDDEN_SNIPPETS = (
    "op.add_column(",
    "batch.add_column(",
    "ADD COLUMN client_request_id",  # unconditional; IF NOT EXISTS form is required
)


def _print_migration_fingerprint() -> None:
    build = _BUILD_ID.read_text(encoding="utf-8").strip() if _BUILD_ID.is_file() else "missing"
    channel = (settings.RIBDIGI_RELEASE_CHANNEL or "").strip() or "unset"
    runtime_build = (settings.RIBDIGI_BUILD_ID or "").strip() or "unset"
    print(f"bootstrap: RIBDIGI_RELEASE_CHANNEL={channel}")
    print(f"bootstrap: RIBDIGI_BUILD_ID(runtime)={runtime_build}")
    print(f"bootstrap: RIBDIGI_BUILD_ID(image)={build}")
    if settings.APP_ENV.lower() == "production" and channel != "production":
        print(
            "bootstrap: ERROR production APP_ENV requires RIBDIGI_RELEASE_CHANNEL=production "
            "(Dokploy must deploy Git branch `production`, not `main`).",
            file=sys.stderr,
        )
        sys.exit(5)
    if not _MIG_0107.is_file():
        print(
            "bootstrap: ERROR missing commercial migration 20260917_0107 — "
            "this image is not the latest ERP (deploy branch `production`).",
            file=sys.stderr,
        )
        sys.exit(6)
    if not _MIG_0106.is_file():
        print(f"bootstrap: ERROR missing {_MIG_0106}", file=sys.stderr)
        sys.exit(2)
    text = _MIG_0106.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    print(f"bootstrap: 20260917_0106 sha256_16={digest} path={_MIG_0106}")
    missing = [m for m in _REQUIRED_MARKERS if m not in text]
    if missing:
        print(
            "bootstrap: ERROR migrate image is stale — idempotent 0106 markers missing: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "bootstrap: Rebuild the backend/migrate image without cache "
            "so Alembic ships IF NOT EXISTS (not op.add_column).",
            file=sys.stderr,
        )
        sys.exit(3)
    forbidden = [s for s in _FORBIDDEN_SNIPPETS if s in text]
    if forbidden:
        print(
            "bootstrap: ERROR 0106 still contains forbidden APIs that emit "
            "plain ADD COLUMN: " + ", ".join(forbidden),
            file=sys.stderr,
        )
        sys.exit(4)
    print("bootstrap: commercial ERP migrations 0106/0107 present")
    print("bootstrap: 0106 idempotent markers OK (no op.add_column/batch.add_column)")


def run_alembic() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode == 0:
            print("Alembic migrations applied")
            return True
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"Alembic failed: {exc}", file=sys.stderr)
        return False


async def create_all_fallback() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Fallback create_all completed")


async def ensure_ribdigi_house_active() -> None:
    """Idempotent ops recovery: platform workspace active + contact email."""
    from sqlalchemy import text

    from app.db import SessionLocal

    email = "info@ribdigihouse.com"
    async with SessionLocal() as db:
        result = await db.execute(
            text(
                """
                UPDATE tenants
                SET
                    status = 'active',
                    email = :email,
                    suspended_at = NULL,
                    suspended_reason = NULL,
                    grace_ends_at = NULL
                WHERE
                    slug IN ('platform', 'ribdigi-platform')
                    OR lower(company_name) = lower('Ribdigi House')
                    OR id IN ('platform', 'ribdigi-platform')
                """
            ),
            {"email": email},
        )
        await db.commit()
        print(
            f"bootstrap: ensure Ribdigi House active/email={email} "
            f"rows={result.rowcount}"
        )


async def ensure_remove_outlook_platform_staff() -> None:
    """Idempotent: hard-delete revoked platform staff by email."""
    from sqlalchemy import text

    from app.db import SessionLocal

    target = "arthurbonneyrichard@outlook.com"
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text(
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
                {"email": target},
            )
        ).fetchall()
        ids = [r[0] for r in rows]
        if not ids:
            print(f"bootstrap: platform staff {target} already absent")
            return

        existing = {
            r[0]
            for r in (
                await db.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """
                    )
                )
            ).fetchall()
        }

        child_tables = (
            "auth_sessions",
            "auth_tokens",
            "webauthn_credentials",
            "webauthn_challenges",
            "two_factor_backup_codes",
            "user_store_memberships",
            "notification_preferences",
        )
        null_updates = (
            ("notifications", "user_id"),
            ("pos_devices", "user_id"),
            ("branches", "manager_id"),
            ("departments", "head_user_id"),
            ("stores", "manager_id"),
            ("warehouses", "manager_id"),
        )

        for uid in ids:
            for table in child_tables:
                if table not in existing:
                    continue
                await db.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :uid"),
                    {"uid": uid},
                )
            for table, col in null_updates:
                if table not in existing:
                    continue
                await db.execute(
                    text(f"UPDATE {table} SET {col} = NULL WHERE {col} = :uid"),
                    {"uid": uid},
                )
            await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
        await db.commit()
        print(f"bootstrap: deleted platform staff {target} ids={ids}")


async def main() -> None:
    _print_migration_fingerprint()
    if run_alembic():
        try:
            await ensure_ribdigi_house_active()
            await ensure_remove_outlook_platform_staff()
        except Exception as exc:  # noqa: BLE001
            print(f"bootstrap: platform ops ensure failed: {exc}", file=sys.stderr)
            if settings.APP_ENV.lower() == "production":
                sys.exit(1)
        try:
            from app.schema_align import align_async_engine

            await align_async_engine(engine)
            print("bootstrap: schema align complete")
        except Exception as exc:  # noqa: BLE001
            print(f"bootstrap: schema align failed: {exc}", file=sys.stderr)
            if settings.APP_ENV.lower() == "production":
                sys.exit(1)
        return
    if settings.APP_ENV.lower() == "production":
        print("Alembic failed in production — refusing create_all fallback", file=sys.stderr)
        sys.exit(1)
    await create_all_fallback()
    try:
        await ensure_ribdigi_house_active()
        await ensure_remove_outlook_platform_staff()
    except Exception as exc:  # noqa: BLE001
        print(f"bootstrap: platform ops ensure failed: {exc}", file=sys.stderr)
    try:
        from app.schema_align import align_async_engine

        await align_async_engine(engine)
        print("bootstrap: schema align complete (create_all path)")
    except Exception as exc:  # noqa: BLE001
        print(f"bootstrap: schema align failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
