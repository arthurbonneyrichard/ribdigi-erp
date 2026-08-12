"""AI Business Assistant — secure packaging (provider gate, sanitize, audit).

Fail-closed chat until an approved provider + API key are configured.
Rule-based insights remain available without an external LLM.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.config import settings

APPROVED_PROVIDERS = frozenset({"openai"})
# Dev/test only — never allowed when APP_ENV=production.
DEV_PROVIDERS = frozenset({"mock"})

CHAT_UNCONFIGURED_DETAIL = (
    "AI Business Assistant is not configured. "
    "Configure an approved AI provider before enabling this feature."
)

# Heuristic prompt-injection / exfil patterns (SECURITY_GUIDE §13).
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
        r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?)",
        r"you\s+are\s+now\s+(dan|unrestricted|jailbroken)",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"(dump|exfiltrate|leak)\s+(all\s+)?(api\s*keys?|secrets?|passwords?|tokens?)",
        r"show\s+me\s+(the\s+)?(api\s*key|secret\s+key|jwt_secret)",
        r"print\s+env(ironment)?\s+variables?",
    )
)

_SECRETISH = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|token|authorization)\s*[:=]\s*\S+"
)


def max_message_chars() -> int:
    raw = int(getattr(settings, "AI_MAX_MESSAGE_CHARS", 16000) or 16000)
    return max(1, raw)


def provider_name() -> str:
    return (getattr(settings, "AI_PROVIDER", "none") or "none").strip().lower()


def api_key_configured() -> bool:
    key = (getattr(settings, "AI_API_KEY", "") or "").strip()
    if not key:
        return False
    weak = {"", "change-me", "changeme", "replace-me", "your-api-key", "sk-test"}
    return key.lower() not in weak and len(key) >= 8


def chat_enabled() -> bool:
    """True only when feature flag + approved provider + key are present."""
    if not bool(getattr(settings, "AI_ENABLED", False)):
        return False
    provider = provider_name()
    if provider in APPROVED_PROVIDERS and api_key_configured():
        return True
    env = (getattr(settings, "APP_ENV", "development") or "development").lower()
    if env != "production" and provider in DEV_PROVIDERS:
        return True
    return False


def status_payload() -> dict[str, Any]:
    provider = provider_name()
    enabled = bool(getattr(settings, "AI_ENABLED", False))
    return {
        "ai_enabled": enabled,
        "provider": provider if provider not in {"", "none"} else "none",
        "chat_available": chat_enabled(),
        "insights_available": True,
        "max_message_chars": max_message_chars(),
        "api_key_configured": api_key_configured() if enabled else False,
        "approved_providers": sorted(APPROVED_PROVIDERS),
    }


def prompt_sha256(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def redacted_preview(message: str, *, limit: int = 80) -> str:
    cleaned = _SECRETISH.sub(r"\1=[REDACTED]", message or "")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def find_injection(message: str) -> str | None:
    text = message or ""
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return pat.pattern
    return None


def parse_chat_message(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON body required")
    raw = payload.get("message")
    if raw is None:
        raw = payload.get("prompt")
    if raw is None:
        raise HTTPException(status_code=422, detail="message is required")
    if not isinstance(raw, str):
        raise HTTPException(status_code=422, detail="message must be a string")
    message = raw.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")
    limit = max_message_chars()
    if len(message) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"message exceeds maximum length of {limit} characters",
        )
    return message


async def record_query(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    endpoint: str,
    status: str,
    message: str | None = None,
    blocked_reason: str | None = None,
    insight_count: int | None = None,
    details: dict | None = None,
) -> m.AiQuery:
    preview = redacted_preview(message) if message else None
    digest = prompt_sha256(message) if message else None
    row = m.AiQuery(
        tenant_id=tenant_id,
        user_id=user_id,
        endpoint=endpoint,
        status=status,
        prompt_sha256=digest,
        prompt_preview=preview,
        message_length=len(message) if message else 0,
        blocked_reason=blocked_reason,
        insight_count=insight_count,
        details=details or {},
    )
    db.add(row)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="ai",
        action=f"ai.{endpoint}.{status}",
        entity="ai_query",
        entity_id=row.id,
        details={
            "endpoint": endpoint,
            "status": status,
            "prompt_sha256": digest,
            "message_length": row.message_length,
            "blocked_reason": blocked_reason,
            "insight_count": insight_count,
            **(details or {}),
        },
    )
    return row


def build_insight_notes(dash: dict) -> list[str]:
    notes: list[str] = []
    low = int(dash.get("low_stock") or 0)
    if low > 0:
        notes.append(f"{low} product(s) are at or below reorder level.")
    expenses = float(dash.get("total_expenses") or 0)
    sales = float(dash.get("total_sales") or 0)
    if expenses > sales and sales > 0:
        notes.append("Expenses currently exceed recorded sales.")
    return notes or [
        "No urgent anomaly detected from the currently configured business rules."
    ]


async def list_queries(
    db: AsyncSession,
    *,
    tenant_id: str,
    limit: int = 50,
) -> list[m.AiQuery]:
    lim = max(1, min(int(limit or 50), 200))
    rows = (
        await db.execute(
            select(m.AiQuery)
            .where(m.AiQuery.tenant_id == tenant_id)
            .order_by(m.AiQuery.created_at.desc())
            .limit(lim)
        )
    ).scalars().all()
    return list(rows)


def serialize_query(row: m.AiQuery) -> dict[str, Any]:
    return {
        "id": row.id,
        "endpoint": row.endpoint,
        "status": row.status,
        "prompt_sha256": row.prompt_sha256,
        "prompt_preview": row.prompt_preview,
        "message_length": row.message_length,
        "blocked_reason": row.blocked_reason,
        "insight_count": row.insight_count,
        "user_id": row.user_id,
        "created_at": row.created_at,
        "details": row.details or {},
    }


async def handle_chat(
    db: AsyncSession,
    *,
    claims: dict,
    payload: dict | None,
) -> dict[str, Any]:
    """Validate + audit chat; fail-closed unless provider configured."""
    tenant_id = claims["tenant_id"]
    user_id = claims.get("sub") or claims.get("user_id")
    message = parse_chat_message(payload)
    injection = find_injection(message)
    if injection:
        await record_query(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint="chat",
            status="blocked",
            message=message,
            blocked_reason="prompt_injection",
            details={"pattern": injection},
        )
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Message rejected by AI prompt safety controls",
        )

    if not chat_enabled():
        await record_query(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint="chat",
            status="unconfigured",
            message=message,
            blocked_reason="provider_not_configured",
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=CHAT_UNCONFIGURED_DETAIL)

    provider = provider_name()
    if provider == "mock":
        answer = (
            "Mock AI reply (development only). "
            "Configure AI_PROVIDER=openai and AI_API_KEY for production chat."
        )
        await record_query(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint="chat",
            status="ok",
            message=message,
            details={"provider": "mock"},
        )
        await db.commit()
        return {"answer": answer, "provider": "mock", "mock": True}

    # Approved external providers: packaging only — do not call until HTTP client lands.
    await record_query(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        endpoint="chat",
        status="provider_pending",
        message=message,
        blocked_reason="provider_client_not_wired",
        details={"provider": provider},
    )
    await db.commit()
    raise HTTPException(
        status_code=503,
        detail=(
            f"AI provider '{provider}' is configured but the chat client is not "
            "enabled in this build. Chat remains fail-closed."
        ),
    )


async def handle_insights(
    db: AsyncSession,
    *,
    claims: dict,
    dash: dict,
) -> dict[str, Any]:
    notes = build_insight_notes(dash)
    await record_query(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub") or claims.get("user_id"),
        endpoint="insights",
        status="ok",
        insight_count=len(notes),
        details={"source": "dashboard_rules"},
    )
    await db.commit()
    return {
        "insights": notes,
        "source": "rule_based",
        "provider_required": False,
    }
