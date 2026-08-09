"""AI prompt/data protections and domain audit (Stage 5 A1 / SECURITY_GUIDE §13)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit

# Free-text AI prompts (reports / assist). Chat keeps a tighter UX cap in the API.
DEFAULT_MAX_PROMPT_LENGTH = 4000
CHAT_MAX_PROMPT_LENGTH = 2000

# Substring match against lowercased prompt (prompt-injection / exfil attempts).
INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "ignore the previous",
    "disregard previous",
    "disregard all prior",
    "forget your instructions",
    "forget previous instructions",
    "you are now",
    "new system prompt",
    "system prompt:",
    "reveal your system",
    "show your system prompt",
    "jailbreak",
    "dan mode",
    "developer mode enabled",
    "exfiltrate",
    "dump all passwords",
    "dump all secrets",
    "show me all api keys",
    "print all credentials",
    "bypass tenant",
    "ignore tenant isolation",
)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(authorization)\s*[:=]\s*\S+"),
)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_for_audit(text: str | None) -> str:
    """Redact secrets and emails before persisting prompt previews in audit details."""
    if text is None:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    out = _EMAIL_RE.sub("[REDACTED_EMAIL]", out)
    return out


def sanitize_ai_prompt(
    text: str | None,
    *,
    field: str = "prompt",
    max_length: int = DEFAULT_MAX_PROMPT_LENGTH,
) -> str:
    """Validate length and block known injection / exfil patterns. Raises ValueError."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    if len(cleaned) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    lowered = cleaned.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lowered:
            raise ValueError("Prompt rejected: potentially unsafe content detected")
    return cleaned


async def audit_ai_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    action: str,
    entity: str = "ai",
    entity_id: str | None = None,
    prompt: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Any:
    body: dict[str, Any] = dict(details or {})
    if prompt is not None:
        body.setdefault("prompt_length", len(prompt))
        body.setdefault("prompt_preview", redact_for_audit(prompt)[:500])
    return await audit.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="ai",
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=body,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def require_safe_ai_prompt(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    text: str | None,
    field: str = "prompt",
    max_length: int = DEFAULT_MAX_PROMPT_LENGTH,
    attempted_action: str = "ai_prompt",
) -> str:
    """Sanitize prompt; on failure audit rejection (committed) and raise HTTP 400."""
    try:
        return sanitize_ai_prompt(text, field=field, max_length=max_length)
    except ValueError as exc:
        await audit_ai_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="ai_prompt_rejected",
            entity="ai_prompt",
            prompt=str(text or ""),
            details={
                "field": field,
                "reason": str(exc),
                "attempted_action": attempted_action,
            },
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
