"""Bootstrap database schema via Alembic, with create_all fallback (non-production only)."""

import asyncio
import subprocess
import sys

from app.config import settings
from app.db import engine
from app.models import Base


def run_alembic() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Alembic migrations applied")
            return True
        print(result.stdout)
        print(result.stderr)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"Alembic failed: {exc}")
        return False


async def create_all_fallback() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Fallback create_all completed")


async def main() -> None:
    if run_alembic():
        return
    if settings.APP_ENV.lower() == "production":
        print("Alembic failed in production — refusing create_all fallback", file=sys.stderr)
        sys.exit(1)
    await create_all_fallback()


if __name__ == "__main__":
    asyncio.run(main())
