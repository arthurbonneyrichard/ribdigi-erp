from datetime import datetime
import pytest

from app.audit import GENESIS_HASH, canonical_payload, compute_integrity_hash


def test_hash_chain_links():
    created = datetime(2026, 8, 8, 12, 0, 0)
    payload1 = canonical_payload(
        tenant_id="t1",
        user_id="u1",
        module="auth",
        action="login",
        entity="user",
        entity_id="u1",
        details={"ok": True},
        created_at=created,
    )
    h1 = compute_integrity_hash(GENESIS_HASH, payload1)
    payload2 = canonical_payload(
        tenant_id="t1",
        user_id="u1",
        module="auth",
        action="logout",
        entity="user",
        entity_id="u1",
        details={},
        created_at=created,
    )
    h2 = compute_integrity_hash(h1, payload2)
    assert h1 != h2
    assert len(h1) == 64
    assert compute_integrity_hash(GENESIS_HASH, payload1) == h1


def test_tamper_changes_hash():
    created = datetime(2026, 8, 8, 12, 0, 0)
    a = canonical_payload(
        tenant_id="t1",
        user_id="u1",
        module="users",
        action="user_created",
        entity="user",
        entity_id="u2",
        details={"role": "cashier"},
        created_at=created,
    )
    b = canonical_payload(
        tenant_id="t1",
        user_id="u1",
        module="users",
        action="user_created",
        entity="user",
        entity_id="u2",
        details={"role": "company_admin"},
        created_at=created,
    )
    assert compute_integrity_hash(GENESIS_HASH, a) != compute_integrity_hash(GENESIS_HASH, b)


@pytest.mark.asyncio
async def test_verify_chain_forks_pass_and_tampering_fails(db_session, seeded):
    """A fork (two entries sharing a parent) is not tampering; an edit or a removed entry is."""
    from datetime import datetime, timedelta

    from sqlalchemy import delete

    from app import audit
    from app import models as m

    tid = seeded["t2"].id
    base = datetime(2026, 1, 1, 12, 0, 0)

    def row(prev, n, action):
        when = base + timedelta(seconds=n)
        payload = canonical_payload(tenant_id=tid, user_id=None, module="audit", action=action,
                                    entity="audit_log", entity_id=None, details={"n": n}, created_at=when)
        h = compute_integrity_hash(prev, payload)
        return m.AuditLog(tenant_id=tid, module="audit", action=action, entity="audit_log", details={"n": n},
                          prev_hash=prev, integrity_hash=h, created_at=when), h

    a, ha = row(GENESIS_HASH, 1, "first")
    b, hb = row(ha, 2, "fork_one")
    c, hc = row(ha, 3, "fork_two")  # same parent as b: the old concurrency fork
    d, _ = row(hc, 4, "after_fork")
    db_session.add_all([a, b, c, d])
    await db_session.commit()
    assert (await audit.verify_chain(db_session, tid))["valid"] is True

    c.details = {"n": 999}  # edited after the fact
    await db_session.commit()
    edited = await audit.verify_chain(db_session, tid)
    assert edited["valid"] is False and edited["broken_at"] == c.id

    c.details = {"n": 3}
    await db_session.commit()
    await db_session.execute(delete(m.AuditLog).where(m.AuditLog.id == c.id))  # removed from the middle
    await db_session.commit()
    removed = await audit.verify_chain(db_session, tid)
    assert removed["valid"] is False and removed["broken_at"] == d.id
