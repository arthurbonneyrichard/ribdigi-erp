from datetime import datetime

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
