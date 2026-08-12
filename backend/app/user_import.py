"""User CSV bulk import (validate + all-or-nothing commit)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.config import settings
from app.rbac import VALID_ROLES, permissions_for_role, serialize_user
from app.security import hash_password, issue_one_time_token, validate_password_strength

TEMPLATE_HEADERS = (
    "full_name",
    "email",
    "phone",
    "role",
    "temporary_password",
)

SAMPLE_ROW = {
    "full_name": "Ada Cashier",
    "email": "ada.cashier@example.com",
    "phone": "",
    "role": "cashier",
    "temporary_password": "TempPass1!",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Tenant operators may assign these via CSV; super_admin blocked unless actor is super_admin.
ASSIGNABLE_ROLES = frozenset(VALID_ROLES) - {"super_admin"}


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(TEMPLATE_HEADERS))
    writer.writeheader()
    writer.writerow(SAMPLE_ROW)
    return buf.getvalue()


def _norm_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def parse_csv_rows(content: str) -> list[dict[str, str]]:
    text = (content or "").lstrip("\ufeff")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty CSV")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is missing a header row")
    mapping = {_norm_header(h): h for h in reader.fieldnames if h}
    # Accept password as alias for temporary_password
    if "password" in mapping and "temporary_password" not in mapping:
        mapping["temporary_password"] = mapping["password"]
    required = ("full_name", "email", "role", "temporary_password")
    missing = [c for c in required if c not in mapping]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV must include columns: {', '.join(required)}",
        )
    rows: list[dict[str, str]] = []
    for raw in reader:
        if not any((v or "").strip() for v in raw.values()):
            continue
        rows.append(
            {
                key: (raw.get(mapping[key]) or "").strip() if key in mapping else ""
                for key in TEMPLATE_HEADERS
            }
        )
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 500:
        raise HTTPException(status_code=400, detail="CSV exceeds 500 row limit")
    return rows


async def _email_exists(db: AsyncSession, tenant_id: str, email: str) -> bool:
    hit = (
        await db.execute(
            select(m.User.id).where(
                m.User.tenant_id == tenant_id,
                func.lower(m.User.email) == email.lower(),
            )
        )
    ).scalar_one_or_none()
    return hit is not None


async def validate_import_rows(
    db: AsyncSession,
    *,
    tenant_id: str,
    rows: list[dict[str, str]],
    actor_role: str | None = None,
) -> dict[str, Any]:
    report_rows: list[dict[str, Any]] = []
    seen_emails: set[str] = set()
    prepared: list[dict[str, Any]] = []
    actor = (actor_role or "").strip()

    for idx, raw in enumerate(rows, start=2):
        errors: list[str] = []
        full_name = (raw.get("full_name") or "").strip()
        email = (raw.get("email") or "").strip().lower()
        phone = (raw.get("phone") or "").strip() or None
        role = (raw.get("role") or "").strip().lower()
        password = raw.get("temporary_password") or ""

        if not full_name:
            errors.append("full_name is required")
        if not email:
            errors.append("email is required")
        elif not EMAIL_RE.match(email):
            errors.append("email is invalid")
        if email and email in seen_emails:
            errors.append("duplicate email in file")
        if email:
            seen_emails.add(email)

        if not role:
            errors.append("role is required")
        elif role == "super_admin":
            if actor != "super_admin":
                errors.append("only super_admin can assign super_admin")
            elif role not in VALID_ROLES:
                errors.append("unknown role")
        elif role not in ASSIGNABLE_ROLES:
            errors.append(f"unknown role (allowed: {', '.join(sorted(ASSIGNABLE_ROLES))})")

        if not password:
            errors.append("temporary_password is required")
        else:
            try:
                validate_password_strength(password)
            except HTTPException as exc:
                errors.append(str(exc.detail))

        if email and await _email_exists(db, tenant_id, email):
            errors.append("email already exists")

        ok = not errors
        report_rows.append(
            {
                "line": idx,
                "email": email,
                "full_name": full_name,
                "role": role,
                "ok": ok,
                "errors": errors,
            }
        )
        if ok:
            prepared.append(
                {
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                    "password": password,
                }
            )

    error_count = sum(1 for r in report_rows if not r["ok"])
    return {
        "total_rows": len(report_rows),
        "valid_rows": len(prepared),
        "error_rows": error_count,
        "can_commit": error_count == 0 and len(prepared) > 0,
        "rows": report_rows,
        "_prepared": prepared,
    }


async def commit_import(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str,
    prepared: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app import emailer

    created: list[dict[str, Any]] = []
    for data in prepared:
        user = m.User(
            tenant_id=tenant_id,
            email=data["email"],
            full_name=data["full_name"],
            phone=data.get("phone"),
            password_hash=hash_password(data["password"]),
            role=data["role"],
            permissions=permissions_for_role(data["role"]),
            email_verified=False,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        raw, token_hash, expires = issue_one_time_token()
        db.add(
            m.AuthToken(
                tenant_id=tenant_id,
                user_id=user.id,
                purpose="email_verify",
                token_hash=token_hash,
                expires_at=expires,
            )
        )
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            module="users",
            action="user_imported",
            entity="user",
            entity_id=user.id,
            details={"email": user.email, "role": user.role},
        )
        email_result = await emailer.send_verification_email(to=user.email, token=raw)
        row_out = {
            "id": user.id,
            "user": serialize_user(user),
            "email": {"sent": email_result.sent, "mode": email_result.mode},
        }
        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            row_out["email_verification_token"] = raw
        created.append(row_out)
    return created
