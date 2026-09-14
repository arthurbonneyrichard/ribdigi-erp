"""CLI: seed the live customer-demo tenant (opt-in).

Usage (from backend/ with PYTHONPATH set):

  ALLOW_DEMO_TENANT_SEED=true python -m scripts.seed_demo_tenant --dry-run
  ALLOW_DEMO_TENANT_SEED=true \\
    DEMO_OWNER_PASSWORD='YourStrongPass1!' \\
    DEMO_CASHIER_PASSWORD='YourStrongPass1!' \\
    python -m scripts.seed_demo_tenant

See docs/DEMO_ACCOUNT.md. Forbidden when APP_ENV=production.
Does not enable ALLOW_PUBLIC_TENANT_SIGNUP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.db import SessionLocal
from app.demo_tenant_seed import config_from_env, seed_demo_tenant


async def _run(dry_run: bool) -> int:
    cfg = config_from_env()
    async with SessionLocal() as db:
        try:
            result = await seed_demo_tenant(db, cfg, dry_run=dry_run, commit=not dry_run)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    # Never print plaintext passwords
    print(json.dumps(result, indent=2, default=str))
    if not dry_run:
        print(
            "Demo tenant ready. Login with tenant slug + owner/cashier email. "
            "Passwords come from DEMO_*_PASSWORD env (or documented defaults). "
            "Change after first login.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed live customer-demo tenant (opt-in)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan only; no database writes",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
