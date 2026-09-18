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
_BUILD_ID = Path("/app/.build-id")
_REQUIRED_MARKERS = (
    "RIBDIGI_0106_IF_NOT_EXISTS_V2",
    "ADD COLUMN IF NOT EXISTS client_request_id",
)


def _print_migration_fingerprint() -> None:
    build = _BUILD_ID.read_text(encoding="utf-8").strip() if _BUILD_ID.is_file() else "missing"
    print(f"bootstrap: RIBDIGI_BUILD_ID={build}")
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
            "(Dokploy → Redeploy with rebuild) so Alembic ships IF NOT EXISTS.",
            file=sys.stderr,
        )
        sys.exit(3)
    print("bootstrap: 0106 idempotent markers OK")


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


async def main() -> None:
    _print_migration_fingerprint()
    if run_alembic():
        return
    if settings.APP_ENV.lower() == "production":
        print("Alembic failed in production — refusing create_all fallback", file=sys.stderr)
        sys.exit(1)
    await create_all_fallback()


if __name__ == "__main__":
    asyncio.run(main())
