"""Ops check: append N audit events concurrently for one company and confirm they form one unbroken chain.

usage (inside the backend container): python scripts/check_audit_chain_concurrency.py <tenant-slug> [N]
Writes N `audit_chain_concurrency_check` events for that company. Exit code 1 if the new events fork.
"""
import asyncio
import sys

from sqlalchemy import select, text

from app import audit
from app import models as m
from app.db import SessionLocal


async def one(tenant_id: str, i: int) -> None:
    async with SessionLocal() as db:
        await audit.record_event(
            db, tenant_id=tenant_id, action="audit_chain_concurrency_check", entity="audit_log",
            module="audit", details={"n": i},
        )
        await db.commit()


async def main(slug: str, n: int) -> int:
    async with SessionLocal() as db:
        tenant_id = (await db.execute(select(m.Tenant.id).where(m.Tenant.slug == slug))).scalar_one()
    await asyncio.gather(*(one(tenant_id, i) for i in range(n)))
    async with SessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT prev_hash, integrity_hash FROM audit_logs WHERE tenant_id=:t AND action='audit_chain_concurrency_check' "
            "ORDER BY created_at DESC, id DESC LIMIT :n"), {"t": tenant_id, "n": n})).all()
    rows = list(reversed(rows))
    forks = sum(1 for a, b in zip(rows, rows[1:]) if b.prev_hash != a.integrity_hash)
    print(f"{n} concurrent events, links broken: {forks}")
    return 1 if forks else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20)))
