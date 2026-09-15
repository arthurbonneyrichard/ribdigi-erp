"""Serialize approval mutations within a single process.

``SELECT FOR UPDATE`` serializes multi-worker Postgres races through the end of
the DB transaction. SQLite (test DB) ignores row locks across concurrent async
sessions on a shared StaticPool, so we add a per-entity asyncio lock the same
way ``store_entitlements`` does for store create/activate.

Locks are keyed by the running event loop so pytest's per-test loops do not
reuse closed-loop ``asyncio.Lock`` objects.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

_locks: dict[tuple[int, str], asyncio.Lock] = {}
_locks_mu = threading.Lock()


def _lock_for(kind: str, tenant_id: str, entity_id: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    key = (id(loop), f"{kind}:{tenant_id}:{entity_id}")
    with _locks_mu:
        lock = _locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _locks[key] = lock
        return lock


@asynccontextmanager
async def expense_approval_lock(tenant_id: str, expense_id: str) -> AsyncIterator[None]:
    """Serialize expense approve/reject for one expense inside a single process."""
    lock = _lock_for("expense", tenant_id, expense_id)
    async with lock:
        yield


@asynccontextmanager
async def purchase_request_approval_lock(tenant_id: str, request_id: str) -> AsyncIterator[None]:
    """Serialize PR approve/reject/convert for one request inside a single process."""
    lock = _lock_for("purchase_request", tenant_id, request_id)
    async with lock:
        yield
