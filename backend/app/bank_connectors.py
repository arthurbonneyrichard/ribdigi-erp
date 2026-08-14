"""Direct bank feed connectors — sync provider transactions into bank reconciliation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

PROVIDERS = frozenset({"mock", "http_json"})


def _encrypt(plain: str) -> str:
    from app.totp import encrypt_secret

    return encrypt_secret(plain)


def _decrypt(token: str) -> str:
    from app.totp import decrypt_secret

    return decrypt_secret(token)


def serialize_connection(row: m.BankAccountConnection, *, include_secrets: bool = False) -> dict:
    data = {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "account_id": row.account_id,
        "provider": row.provider,
        "display_name": row.display_name or "Bank connection",
        "external_account_id": row.external_account_id,
        "feed_url": row.feed_url,
        "has_credentials": bool(row.credentials_enc),
        "auto_sync": bool(row.auto_sync),
        "auto_match_after_sync": bool(row.auto_match_after_sync),
        "sync_lookback_days": int(row.sync_lookback_days or 30),
        "is_active": bool(row.is_active),
        "last_synced_at": row.last_synced_at,
        "last_sync_status": row.last_sync_status,
        "last_sync_error": row.last_sync_error,
        "last_statement_id": row.last_statement_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if include_secrets:
        data["credentials_configured"] = bool(row.credentials_enc)
    return data


async def get_connection(
    db: AsyncSession,
    *,
    tenant_id: str,
    connection_id: str,
    company_id: str | None = None,
) -> m.BankAccountConnection:
    row = (
        await db.execute(
            select(m.BankAccountConnection).where(
                m.BankAccountConnection.id == connection_id,
                m.BankAccountConnection.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Bank connection not found")
    if company_id and row.company_id and row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Bank connection not found")
    return row


async def list_connections(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
    company_id: str | None = None,
) -> list[m.BankAccountConnection]:
    """Stage 126 C1 — is_active / active_only for honest inactive-only bank connection lists."""
    stmt = select(m.BankAccountConnection).where(
        m.BankAccountConnection.tenant_id == tenant_id
    )
    if company_id:
        stmt = stmt.where(m.BankAccountConnection.company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(m.BankAccountConnection.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.BankAccountConnection.is_active.is_(True))
    return list(
        (await db.execute(stmt.order_by(m.BankAccountConnection.created_at.desc())))
        .scalars()
        .all()
    )


def _normalize_provider(provider: str | None) -> str:
    value = (provider or "mock").strip().lower()
    if value not in PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider must be one of: {', '.join(sorted(PROVIDERS))}",
        )
    return value


async def create_connection(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    provider: str = "mock",
    display_name: str | None = None,
    external_account_id: str | None = None,
    feed_url: str | None = None,
    access_token: str | None = None,
    auto_sync: bool = True,
    auto_match_after_sync: bool = True,
    sync_lookback_days: int = 30,
    company_id: str | None = None,
) -> m.BankAccountConnection:
    from app.bank_recon import get_liquid_account

    await get_liquid_account(db, tenant_id, account_id, company_id=company_id)
    existing = (
        await db.execute(
            select(m.BankAccountConnection).where(
                m.BankAccountConnection.tenant_id == tenant_id,
                m.BankAccountConnection.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A bank connection already exists for this GL account",
        )

    prov = _normalize_provider(provider)
    if prov == "http_json" and not (feed_url or "").strip():
        raise HTTPException(status_code=400, detail="feed_url is required for http_json provider")

    lookback = max(1, min(int(sync_lookback_days or 30), 365))
    creds = None
    if access_token:
        creds = _encrypt(json.dumps({"access_token": access_token.strip()}))

    now = datetime.utcnow()
    row = m.BankAccountConnection(
        tenant_id=tenant_id,
        company_id=company_id,
        account_id=account_id,
        provider=prov,
        display_name=(display_name or "").strip() or None,
        external_account_id=(external_account_id or "").strip() or None,
        feed_url=(feed_url or "").strip() or None,
        credentials_enc=creds,
        auto_sync=bool(auto_sync),
        auto_match_after_sync=bool(auto_match_after_sync),
        sync_lookback_days=lookback,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def update_connection(
    db: AsyncSession,
    *,
    tenant_id: str,
    connection_id: str,
    payload: dict,
    company_id: str | None = None,
) -> m.BankAccountConnection:
    row = await get_connection(
        db, tenant_id=tenant_id, connection_id=connection_id, company_id=company_id
    )
    if "display_name" in payload and payload["display_name"] is not None:
        row.display_name = str(payload["display_name"]).strip() or None
    if "external_account_id" in payload and payload["external_account_id"] is not None:
        row.external_account_id = str(payload["external_account_id"]).strip() or None
    if "feed_url" in payload and payload["feed_url"] is not None:
        row.feed_url = str(payload["feed_url"]).strip() or None
    if "provider" in payload and payload["provider"] is not None:
        row.provider = _normalize_provider(payload["provider"])
    if "auto_sync" in payload and payload["auto_sync"] is not None:
        row.auto_sync = bool(payload["auto_sync"])
    if "auto_match_after_sync" in payload and payload["auto_match_after_sync"] is not None:
        row.auto_match_after_sync = bool(payload["auto_match_after_sync"])
    if "sync_lookback_days" in payload and payload["sync_lookback_days"] is not None:
        row.sync_lookback_days = max(1, min(int(payload["sync_lookback_days"]), 365))
    if "is_active" in payload and payload["is_active"] is not None:
        row.is_active = bool(payload["is_active"])
    if payload.get("access_token"):
        row.credentials_enc = _encrypt(
            json.dumps({"access_token": str(payload["access_token"]).strip()})
        )
    if payload.get("clear_credentials"):
        row.credentials_enc = None
    if row.provider == "http_json" and not (row.feed_url or "").strip():
        raise HTTPException(status_code=400, detail="feed_url is required for http_json provider")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def delete_connection(
    db: AsyncSession,
    *,
    tenant_id: str,
    connection_id: str,
    company_id: str | None = None,
) -> None:
    row = await get_connection(
        db, tenant_id=tenant_id, connection_id=connection_id, company_id=company_id
    )
    await db.delete(row)
    await db.flush()


def _credentials(row: m.BankAccountConnection) -> dict:
    if not row.credentials_enc:
        return {}
    try:
        return json.loads(_decrypt(row.credentials_enc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unable to decrypt bank credentials: {exc}") from exc


def _normalize_txn(raw: dict) -> dict | None:
    """Map provider row → bank_recon line shape."""
    amount = raw.get("amount")
    if amount is None and ("debit" in raw or "credit" in raw):
        debit = float(raw.get("debit") or 0)
        credit = float(raw.get("credit") or 0)
        amount = credit - debit
    if amount is None:
        return None
    amount = float(amount)
    if abs(amount) < 1e-9:
        return None
    txn_date = raw.get("txn_date") or raw.get("date") or raw.get("posted_at")
    if not txn_date:
        return None
    ref = (
        raw.get("external_ref")
        or raw.get("id")
        or raw.get("transaction_id")
        or raw.get("reference")
    )
    if ref is not None:
        ref = str(ref).strip()[:120] or None
    return {
        "txn_date": txn_date,
        "amount": amount,
        "description": (raw.get("description") or raw.get("memo") or raw.get("narrative") or "").strip()
        or None,
        "external_ref": ref,
    }


async def fetch_provider_transactions(
    row: m.BankAccountConnection, *, since: datetime
) -> tuple[str, list[dict], float | None, float | None]:
    """Return (provider, normalized lines, opening, closing)."""
    provider = (row.provider or "mock").strip().lower()
    if provider == "mock":
        return "mock", _mock_transactions(row, since=since), None, None
    if provider == "http_json":
        return await _fetch_http_json(row, since=since)
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


def _mock_transactions(row: m.BankAccountConnection, *, since: datetime) -> list[dict]:
    """Deterministic sample feed for tests and local development.

    Emits one deposit + one withdrawal per day from max(since, today-7) through today
    so re-syncs share stable external_ref values and dedupe correctly.
    """
    seed = (row.external_account_id or row.account_id or "acct")[:32]
    today = datetime.utcnow().date()
    start = since.date() if hasattr(since, "date") else since
    if not hasattr(start, "isoformat"):
        start = today
    window_start = max(start, today - timedelta(days=7))
    lines: list[dict] = []
    day = window_start
    while day <= today:
        stamp = day.isoformat()
        h = hashlib.sha256(f"{seed}:{stamp}".encode()).hexdigest()[:10]
        base_amt = (int(h[:2], 16) % 90) + 10
        lines.append(
            {
                "txn_date": stamp,
                "amount": float(base_amt),
                "description": f"Mock deposit {h}",
                "external_ref": f"mock-{seed}-{stamp}-in",
            }
        )
        lines.append(
            {
                "txn_date": stamp,
                "amount": -float((base_amt // 2) or 5),
                "description": f"Mock withdrawal {h}",
                "external_ref": f"mock-{seed}-{stamp}-out",
            }
        )
        day = day + timedelta(days=1)
    return lines


async def _fetch_http_json(
    row: m.BankAccountConnection, *, since: datetime
) -> tuple[str, list[dict], float | None, float | None]:
    import httpx

    url = (row.feed_url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="feed_url is not configured")
    creds = _credentials(row)
    headers = {"Accept": "application/json"}
    token = creds.get("access_token") or creds.get("api_key")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {
        "since": since.date().isoformat() if hasattr(since, "date") else str(since)[:10],
    }
    if row.external_account_id:
        params["account_id"] = row.external_account_id
    timeout = float(settings.BANK_FEED_TIMEOUT_SECONDS or 30)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Bank feed request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Bank feed returned invalid JSON: {exc}") from exc

    if isinstance(data, list):
        raw_lines = data
        opening = closing = None
    elif isinstance(data, dict):
        raw_lines = (
            data.get("transactions")
            or data.get("lines")
            or data.get("data")
            or []
        )
        opening = data.get("opening_balance")
        closing = data.get("closing_balance")
    else:
        raise HTTPException(status_code=502, detail="Bank feed JSON must be an object or array")

    lines: list[dict] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            continue
        norm = _normalize_txn(raw)
        if norm:
            lines.append(norm)
    return "http_json", lines, (
        float(opening) if opening is not None else None
    ), (float(closing) if closing is not None else None)


async def _known_external_refs(
    db: AsyncSession, *, tenant_id: str, account_id: str
) -> set[str]:
    rows = (
        await db.execute(
            select(m.BankStatementLine.external_ref)
            .join(m.BankStatement, m.BankStatement.id == m.BankStatementLine.statement_id)
            .where(
                m.BankStatementLine.tenant_id == tenant_id,
                m.BankStatement.account_id == account_id,
                m.BankStatementLine.external_ref.is_not(None),
            )
        )
    ).scalars().all()
    return {str(r) for r in rows if r}


async def sync_connection(
    db: AsyncSession,
    *,
    tenant_id: str,
    connection_id: str,
    user_id: str | None = None,
    force: bool = False,
    company_id: str | None = None,
) -> dict:
    """Pull provider transactions and create a bank statement (deduped by external_ref)."""
    if not bool(settings.BANK_FEED_SYNC_ENABLED):
        raise HTTPException(status_code=503, detail="Bank feed sync is disabled")

    from app import bank_recon as bank_recon_svc

    row = await get_connection(
        db, tenant_id=tenant_id, connection_id=connection_id, company_id=company_id
    )
    if not row.is_active and not force:
        raise HTTPException(status_code=400, detail="Bank connection is inactive")

    lookback = max(1, int(row.sync_lookback_days or 30))
    if row.last_synced_at:
        since = row.last_synced_at - timedelta(days=1)
    else:
        since = datetime.utcnow() - timedelta(days=lookback)

    try:
        provider, lines, opening, closing = await fetch_provider_transactions(row, since=since)
        known = await _known_external_refs(db, tenant_id=tenant_id, account_id=row.account_id)
        fresh: list[dict] = []
        skipped = 0
        for ln in lines:
            ref = ln.get("external_ref")
            if ref and ref in known:
                skipped += 1
                continue
            fresh.append(ln)
            if ref:
                known.add(ref)

        result: dict = {
            "connection_id": row.id,
            "provider": provider,
            "fetched": len(lines),
            "imported": 0,
            "skipped_duplicates": skipped,
            "statement_id": None,
            "auto_match": None,
        }

        if not fresh:
            row.last_synced_at = datetime.utcnow()
            row.last_sync_status = "ok"
            row.last_sync_error = None
            row.updated_at = datetime.utcnow()
            await db.flush()
            result["message"] = "No new transactions"
            return result

        net = round(sum(float(ln["amount"]) for ln in fresh), 2)
        open_bal = float(opening) if opening is not None else 0.0
        close_bal = float(closing) if closing is not None else round(open_bal + net, 2)
        stmt_date = max(ln["txn_date"] for ln in fresh)
        stmt_company_id = company_id or row.company_id

        stmt = await bank_recon_svc.create_statement(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            account_id=row.account_id,
            statement_date=stmt_date,
            opening_balance=open_bal,
            closing_balance=close_bal,
            notes=f"API sync ({provider}) — {len(fresh)} new lines",
            lines=fresh,
            company_id=stmt_company_id,
        )
        result["imported"] = len(fresh)
        result["statement_id"] = stmt.id
        row.last_statement_id = stmt.id

        if row.auto_match_after_sync:
            match_meta = await bank_recon_svc.apply_auto_matches(
                db, tenant_id=tenant_id, statement_id=stmt.id, min_confidence="high"
            )
            result["auto_match"] = match_meta

        row.last_synced_at = datetime.utcnow()
        row.last_sync_status = "ok"
        row.last_sync_error = None
        row.updated_at = datetime.utcnow()
        await db.flush()
        return result
    except HTTPException as exc:
        row.last_sync_status = "error"
        row.last_sync_error = str(exc.detail)
        row.updated_at = datetime.utcnow()
        await db.flush()
        raise
    except Exception as exc:  # noqa: BLE001
        row.last_sync_status = "error"
        row.last_sync_error = str(exc)
        row.updated_at = datetime.utcnow()
        await db.flush()
        raise HTTPException(status_code=502, detail=f"Bank sync failed: {exc}") from exc


async def sync_tenant_auto_connections(
    db: AsyncSession, *, tenant_id: str, user_id: str | None = None
) -> dict:
    rows = (
        await db.execute(
            select(m.BankAccountConnection).where(
                m.BankAccountConnection.tenant_id == tenant_id,
                m.BankAccountConnection.is_active.is_(True),
                m.BankAccountConnection.auto_sync.is_(True),
            )
        )
    ).scalars().all()
    synced = []
    errors = []
    for row in rows:
        try:
            outcome = await sync_connection(
                db, tenant_id=tenant_id, connection_id=row.id, user_id=user_id
            )
            synced.append(outcome)
        except HTTPException as exc:
            errors.append({"connection_id": row.id, "error": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001
            errors.append({"connection_id": row.id, "error": str(exc)})
    return {
        "connection_count": len(rows),
        "synced": len(synced),
        "errors": len(errors),
        "results": synced,
        "failures": errors,
    }


def settings_payload() -> dict:
    return {
        "sync_enabled": bool(settings.BANK_FEED_SYNC_ENABLED),
        "providers": sorted(PROVIDERS),
        "timeout_seconds": float(settings.BANK_FEED_TIMEOUT_SECONDS or 30),
        "celery_interval_minutes": int(settings.CELERY_BANK_FEED_INTERVAL_MINUTES or 360),
    }
