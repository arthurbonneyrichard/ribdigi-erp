"""POS cash drawer hardware abstraction (mock / ESC-POS network / browser bridge)."""

from __future__ import annotations

import base64
import logging
import socket
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

logger = logging.getLogger(__name__)

DRAWER_MODES = frozenset({"none", "mock", "network", "browser_bridge"})
# ESC/POS: ESC p m t1 t2 — open drawer on pin 0
DEFAULT_KICK = bytes([0x1B, 0x70, 0x00, 0x19, 0xFA])


def kick_bytes() -> bytes:
    return DEFAULT_KICK


def kick_base64() -> str:
    return base64.b64encode(kick_bytes()).decode("ascii")


def kick_hex() -> str:
    return kick_bytes().hex()


def normalize_mode(mode: str | None) -> str:
    value = (mode or "none").strip().lower().replace("-", "_")
    if value not in DRAWER_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"drawer_mode must be one of: {', '.join(sorted(DRAWER_MODES))}",
        )
    return value


def serialize_drawer_settings(store: m.Store | None) -> dict:
    if not store:
        return {
            "drawer_mode": (settings.POS_DRAWER_FALLBACK_MODE or "none").strip().lower(),
            "drawer_host": None,
            "drawer_port": int(settings.POS_DRAWER_DEFAULT_PORT or 9100),
            "drawer_open_on_cash": True,
            "source": "fallback",
        }
    return {
        "drawer_mode": getattr(store, "drawer_mode", None) or "none",
        "drawer_host": getattr(store, "drawer_host", None),
        "drawer_port": int(getattr(store, "drawer_port", None) or 9100),
        "drawer_open_on_cash": bool(getattr(store, "drawer_open_on_cash", True)),
        "source": "store",
        "store_id": store.id,
    }


def _send_network(host: str, port: int, payload: bytes) -> None:
    timeout = float(settings.POS_DRAWER_TIMEOUT_SECONDS or 3)
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.sendall(payload)


def _dispatch(mode: str, *, host: str | None, port: int, reason: str) -> dict:
    payload = kick_bytes()
    result = {
        "ok": True,
        "mode": mode,
        "reason": reason,
        "kick_base64": kick_base64(),
        "kick_hex": kick_hex(),
        "sent_at": datetime.utcnow().isoformat() + "Z",
    }
    if mode == "none":
        result["ok"] = False
        result["skipped"] = True
        result["message"] = "Cash drawer is disabled for this store"
        return result
    if mode == "mock":
        logger.info("Cash drawer mock kick reason=%s", reason)
        result["message"] = "Mock drawer pulse recorded"
        return result
    if mode == "browser_bridge":
        result["message"] = "Kick command ready for browser/local print bridge"
        result["bridge"] = True
        return result
    if mode == "network":
        if not (host or "").strip():
            raise HTTPException(status_code=400, detail="drawer_host is required for network mode")
        try:
            _send_network(host.strip(), port, payload)
        except OSError as exc:
            raise HTTPException(
                status_code=502, detail=f"Cash drawer network pulse failed: {exc}"
            ) from exc
        result["host"] = host.strip()
        result["port"] = int(port)
        result["message"] = "ESC/POS drawer pulse sent"
        return result
    raise HTTPException(status_code=400, detail=f"Unsupported drawer mode: {mode}")


async def resolve_config(
    db: AsyncSession, *, tenant_id: str, store_id: str | None
) -> dict:
    store = None
    if store_id:
        store = await db.get(m.Store, store_id)
        if not store or store.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Store not found")
    cfg = serialize_drawer_settings(store)
    if cfg["drawer_mode"] == "none" and not store_id:
        # Allow ops default for storeless shifts
        fallback = (settings.POS_DRAWER_FALLBACK_MODE or "none").strip().lower()
        if fallback in DRAWER_MODES:
            cfg["drawer_mode"] = fallback
    return cfg


async def open_drawer(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
    reason: str,
    user_id: str | None = None,
    force: bool = False,
    require_specific_reason: bool = False,
) -> dict:
    """Pulse the cash drawer. force=True for manual opens even if mode is none? No — none stays off.

    When require_specific_reason=True (manual POS button), reject blank / placeholder reasons.
    Auto-open on cash sale passes require_specific_reason=False with reason pos_sale:{id}.
    """
    reason_clean = (reason or "").strip()
    if require_specific_reason:
        if len(reason_clean) < 3:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "DRAWER_REASON_REQUIRED",
                    "message": "Drawer open reason is required (min 3 characters)",
                },
            )
        if reason_clean.lower() in {"manual", "n/a", "na", "none", "test"}:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "DRAWER_REASON_REQUIRED",
                    "message": "Provide a specific reason (e.g. change request, no sale)",
                },
            )
    elif not reason_clean:
        reason_clean = "manual"
    if len(reason_clean) > 200:
        raise HTTPException(status_code=400, detail="reason too long")
    cfg = await resolve_config(db, tenant_id=tenant_id, store_id=store_id)
    mode = normalize_mode(cfg.get("drawer_mode"))
    if mode == "none" and not force:
        return {
            "ok": False,
            "skipped": True,
            "mode": "none",
            "reason": reason_clean,
            "message": "Cash drawer disabled",
        }
    try:
        result = _dispatch(
            mode,
            host=cfg.get("drawer_host"),
            port=int(cfg.get("drawer_port") or 9100),
            reason=reason_clean,
        )
    except HTTPException:
        raise
    result["store_id"] = store_id
    result["user_id"] = user_id
    result["reason"] = reason_clean
    return result


async def maybe_open_on_cash_sale(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
    payment_method: str,
    sale_id: str,
    user_id: str | None = None,
) -> dict | None:
    """Open drawer after a cash POS sale when store policy allows. Soft-fail on hardware errors."""
    method = (payment_method or "").strip().lower()
    if method != "cash":
        return None
    cfg = await resolve_config(db, tenant_id=tenant_id, store_id=store_id)
    if not bool(cfg.get("drawer_open_on_cash", True)):
        return {
            "ok": False,
            "skipped": True,
            "mode": cfg.get("drawer_mode"),
            "message": "drawer_open_on_cash is false",
        }
    if normalize_mode(cfg.get("drawer_mode")) == "none":
        return {
            "ok": False,
            "skipped": True,
            "mode": "none",
            "message": "Cash drawer disabled",
        }
    try:
        return await open_drawer(
            db,
            tenant_id=tenant_id,
            store_id=store_id,
            reason=f"pos_sale:{sale_id}",
            user_id=user_id,
        )
    except HTTPException as exc:
        logger.warning("Cash drawer open failed for sale %s: %s", sale_id, exc.detail)
        return {
            "ok": False,
            "error": str(exc.detail),
            "mode": cfg.get("drawer_mode"),
            "kick_base64": kick_base64(),
            "message": "Sale recorded; drawer pulse failed",
        }
