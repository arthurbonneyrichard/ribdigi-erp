"""Offline POS payment safety — cash default; no fabricated provider success (§18)."""

from __future__ import annotations

from fastapi import HTTPException

from app.rbac import has_permission

# Safe offline without supervisor acknowledgment.
OFFLINE_CASH_METHODS = frozenset({"cash"})

# External / provider rails — never claim live approval when queued offline.
OFFLINE_PROVIDER_METHODS = frozenset(
    {
        "card",
        "wallet",
        "bank_transfer",
        "mobile_money",
        "momo",
        "online",
    }
)

OFFLINE_CREDIT_METHOD = "credit"

SUPERVISOR_ROLES = frozenset(
    {
        "store_manager",
        "company_admin",
        "super_admin",
        "sales_officer",
        "accountant",
        "tenant_owner",
        "tenant_admin",
    }
)


def normalize_payment_method(method: str | None) -> str:
    return (method or "cash").strip().lower()


def sale_payment_methods(payload: dict) -> list[str]:
    payments = payload.get("payments")
    if isinstance(payments, list) and payments:
        methods: list[str] = []
        for row in payments:
            if not isinstance(row, dict):
                continue
            methods.append(normalize_payment_method(str(row.get("payment_method") or "cash")))
        return methods or [normalize_payment_method(str(payload.get("payment_method") or "cash"))]
    return [normalize_payment_method(str(payload.get("payment_method") or "cash"))]


def _offline_meta(payload: dict) -> dict:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return nested
    return {}


def _supervisor_ack(payload: dict) -> tuple[bool, str]:
    meta = _offline_meta(payload)
    ack = bool(payload.get("offline_supervisor_ack") or meta.get("offline_supervisor_ack"))
    reason = str(
        payload.get("offline_supervisor_reason") or meta.get("offline_supervisor_reason") or ""
    ).strip()
    return ack, reason


def _credit_cached_ack(payload: dict) -> bool:
    meta = _offline_meta(payload)
    return bool(payload.get("offline_credit_cached_ack") or meta.get("offline_credit_cached_ack"))


def is_supervisor_offline_actor(claims: dict) -> bool:
    role = (claims.get("role") or "cashier").strip().lower()
    if role in SUPERVISOR_ROLES:
        return True
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    for module in ("credit", "expenses", "purchasing"):
        if has_permission(role, module, "approve", overrides=overrides):
            return True
    return False


def validate_offline_pos_sale_payments(payload: dict, *, claims: dict) -> None:
    """Reject unsafe offline payment combinations before record_pos_sale runs."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid pos_sale payload")

    methods = sale_payment_methods(payload)
    ack, reason = _supervisor_ack(payload)

    for method in methods:
        if method in OFFLINE_CASH_METHODS:
            continue

        if method == OFFLINE_CREDIT_METHOD:
            if not (payload.get("party_id") or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "OFFLINE_CREDIT_BLOCKED: Offline credit requires a registered customer "
                        "(party_id)"
                    ),
                )
            if not _credit_cached_ack(payload):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "OFFLINE_CREDIT_BLOCKED: Offline credit requires cached customer "
                        "acknowledgment (revalidated on sync)"
                    ),
                )
            role = (claims.get("role") or "cashier").strip().lower()
            overrides = (
                claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
            )
            if not (
                has_permission(role, "credit", "read", overrides=overrides)
                or has_permission(role, "credit", "write", overrides=overrides)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="OFFLINE_CREDIT_BLOCKED: Missing credit permission for offline credit sale",
                )
            continue

        if method in OFFLINE_PROVIDER_METHODS or method not in OFFLINE_CASH_METHODS:
            if not ack:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "OFFLINE_PAYMENT_BLOCKED: "
                        f"{method} payments cannot be queued offline without supervisor "
                        "acknowledgment — provider success is not verified offline"
                    ),
                )
            if len(reason) < 3:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "OFFLINE_PAYMENT_BLOCKED: Supervisor acknowledgment reason required "
                        "(min 3 characters) for offline provider payments"
                    ),
                )
