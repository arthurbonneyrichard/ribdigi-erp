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


SALES_ANOMALY_PCT = 25.0
MAX_INSIGHT_NOTES = 20


def _pct_delta(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / abs(previous) * 100.0, 1)


def build_insight_notes(dash: dict) -> list[str]:
    """Sync baseline notes from dashboard totals (kept for unit tests / callers)."""
    notes: list[str] = []
    low = int(dash.get("low_stock") or 0)
    if low > 0:
        notes.append(f"{low} product(s) are at or below reorder level.")
    expenses = float(dash.get("total_expenses") or 0)
    sales = float(dash.get("total_sales") or 0)
    if expenses > sales and sales > 0:
        notes.append("Expenses currently exceed recorded sales.")
    notes.extend(_sales_spike_drop_notes(dash))
    return notes or [
        "No urgent anomaly detected from the currently configured business rules."
    ]


def _sales_spike_drop_notes(dash: dict) -> list[str]:
    notes: list[str] = []
    cmp = dash.get("comparisons") or {}
    checks = (
        ("sales_today_pct", "today vs yesterday"),
        ("sales_mtd_pct", "MTD vs prior month"),
    )
    for key, label in checks:
        pct = cmp.get(key)
        if pct is None:
            continue
        try:
            pct_f = float(pct)
        except (TypeError, ValueError):
            continue
        if pct_f >= SALES_ANOMALY_PCT:
            notes.append(f"Sales spike {pct_f:g}% ({label}).")
        elif pct_f <= -SALES_ANOMALY_PCT:
            notes.append(f"Sales drop {pct_f:g}% ({label}).")

    daily = dash.get("daily_sales") or []
    if len(daily) >= 14:
        recent = sum(float(d.get("sales") or 0) for d in daily[-7:])
        prior = sum(float(d.get("sales") or 0) for d in daily[-14:-7])
        wow = _pct_delta(recent, prior)
        if wow is not None and wow >= SALES_ANOMALY_PCT:
            notes.append(f"Sales spike {wow:g}% (last 7 days vs prior 7).")
        elif wow is not None and wow <= -SALES_ANOMALY_PCT:
            notes.append(f"Sales drop {wow:g}% (last 7 days vs prior 7).")
    return notes


async def compose_insights(
    db: AsyncSession,
    *,
    tenant_id: str,
    dash: dict,
) -> dict[str, Any]:
    """Compose BR-21.2 rule-based insights from dashboard + expense + inventory signals."""
    from app import ai_expenses as ai_expenses_svc
    from app.ai_inventory import build_product_forecasts

    signals: list[dict[str, Any]] = []
    notes: list[str] = []

    def add(kind: str, headline: str, detail: str | None = None) -> None:
        signals.append({"kind": kind, "headline": headline, "detail": detail})
        notes.append(headline if not detail else f"{headline} — {detail}")

    low = int(dash.get("low_stock") or 0)
    if low > 0:
        add("stock", f"{low} product(s) are at or below reorder level.")

    expenses = float(dash.get("total_expenses") or 0)
    sales = float(dash.get("total_sales") or 0)
    if expenses > sales and sales > 0:
        add("expense_anomaly", "Expenses currently exceed recorded sales.")

    for note in _sales_spike_drop_notes(dash):
        kind = "sales_spike" if "spike" in note.lower() else "sales_drop"
        add(kind, note)

    exp = await ai_expenses_svc.expense_analysis(
        db, tenant_id=tenant_id, actor_user_id=None, audit=False
    )
    for alert in (exp.get("budget_variance_alerts") or [])[:3]:
        add(
            "expense_anomaly",
            f"{alert.get('category') or 'Category'} is {alert.get('variance_pct')}% over budget",
            f"spent {alert.get('spent')} vs {alert.get('budget_scaled')}",
        )
    for unusual in (exp.get("unusual_expenses") or [])[:3]:
        payee = unusual.get("payee") or "payee"
        add(
            "expense_anomaly",
            f"Unusual expense {unusual.get('amount')} ({unusual.get('category') or 'uncategorized'})",
            f"{payee}; {unusual.get('reason') or 'outlier'}",
        )
    for dup in (exp.get("duplicate_candidates") or [])[:2]:
        add(
            "expense_anomaly",
            f"Possible duplicate: {dup.get('payee')} × {dup.get('count')} at {dup.get('amount')}",
            str(dup.get("date") or ""),
        )

    forecasts = await build_product_forecasts(db, tenant_id=tenant_id)
    action_count = 0
    for row in forecasts:
        if action_count >= 5:
            break
        season = row.get("seasonality") or {}
        label = str(season.get("label") or "")
        rising = label in {"rising", "emerging_demand"}
        dts = row.get("days_to_stockout")
        stock = float(row.get("stock_qty") or 0)
        reorder = float(row.get("reorder_level") or 0)
        at_risk = stock <= reorder or (dts is not None and float(dts) <= 14)
        rec_qty = float(row.get("recommended_order_qty") or 0)
        if not (rising and at_risk and rec_qty > 0):
            continue
        ratio = season.get("ratio")
        try:
            ratio_f = float(ratio) if ratio is not None else None
        except (TypeError, ValueError):
            ratio_f = None
        if ratio_f and ratio_f > 1:
            up_txt = f"{round((ratio_f - 1) * 100):g}%"
        else:
            up_txt = "recently"
        detail = None
        if dts is not None:
            detail = f"stockout in ~{dts} days; suggest order {rec_qty:g}"
        elif rec_qty > 0:
            detail = f"suggest order {rec_qty:g}"
        add(
            "action",
            f"Restock {row.get('name') or row.get('sku') or 'product'} — sales up {up_txt} this period",
            detail,
        )
        action_count += 1

    if not notes:
        fallback = "No urgent anomaly detected from the currently configured business rules."
        add("info", fallback)

    return {
        "insights": notes[:MAX_INSIGHT_NOTES],
        "signals": signals[:MAX_INSIGHT_NOTES],
        "source": "rule_based",
    }


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
    payload = await compose_insights(db, tenant_id=claims["tenant_id"], dash=dash)
    notes = payload.get("insights") or []
    signals = payload.get("signals") or []
    await record_query(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub") or claims.get("user_id"),
        endpoint="insights",
        status="ok",
        insight_count=len(notes),
        details={
            "source": "composed_rules",
            "signal_kinds": sorted({str(s.get("kind")) for s in signals if s.get("kind")}),
        },
    )
    await db.commit()
    return {
        **payload,
        "provider_required": False,
    }
