"""Bootstrap database schema via Alembic, with create_all fallback."""

import asyncio
import subprocess
import sys

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
    if not run_alembic():
        await create_all_fallback()


if __name__ == "__main__":
    asyncio.run(main())
