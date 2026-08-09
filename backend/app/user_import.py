"""CSV bulk import for users (template + dry-run/commit)."""

from __future__ import annotations

import csv
import io
import re
import secrets
import string
from typing import Any

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import org_units as org_units_svc
from app import roles as roles_svc
from app.rbac import RECORD_SCOPE_KEY, normalize_record_scope
from app.security import hash_password, issue_one_time_token, validate_password_strength

TEMPLATE_COLUMNS = [
    "full_name",
    "email",
    "phone",
    "role",
    "branch_code",
    "department_code",
    "password",
    "record_scope",
]

_EMAIL = TypeAdapter(EmailStr)


def generate_temp_password() -> str:
    """Generate a password that satisfies validate_password_strength."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
            *[secrets.choice(alphabet) for _ in range(8)],
        ]
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        try:
            validate_password_strength(password)
            return password
        except HTTPException:
            continue


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "full_name": "Ada Cashier",
            "email": "ada.cashier@example.com",
            "phone": "+233200000000",
            "role": "cashier",
            "branch_code": "",
            "department_code": "",
            "password": "",
            "record_scope": "own",
        }
    )
    return buf.getvalue()


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def parse_user_csv(content: str) -> list[dict[str, str]]:
    sample = content.lstrip("\ufeff")
    if not sample.strip():
        raise HTTPException(status_code=400, detail="Empty CSV")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    aliases = {
        "name": "full_name",
        "full_name": "full_name",
        "email": "email",
        "phone": "phone",
        "role": "role",
        "branch": "branch_code",
        "branch_code": "branch_code",
        "department": "department_code",
        "department_code": "department_code",
        "password": "password",
        "record_scope": "record_scope",
        "scope": "record_scope",
    }
    header_map: dict[str, str] = {}
    for raw in reader.fieldnames:
        key = aliases.get(_norm_header(raw))
        if key and key not in header_map:
            header_map[key] = raw
    if "full_name" not in header_map or "email" not in header_map:
        raise HTTPException(status_code=400, detail="CSV must include full_name and email columns")

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        if not any((v or "").strip() for v in raw_row.values()):
            continue
        rows.append(
            {
                col: (raw_row.get(header_map[col]) or "").strip() if col in header_map else ""
                for col in TEMPLATE_COLUMNS
            }
        )
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    if len(rows) > 1000:
        raise HTTPException(status_code=400, detail="CSV exceeds maximum of 1000 rows")
    return rows


async def import_users_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str | None,
    content: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    rows = parse_user_csv(content)
    branches = {
        b.code.upper(): b
        for b in (
            await db.execute(select(m.Branch).where(m.Branch.tenant_id == tenant_id))
        ).scalars().all()
    }
    departments = {
        d.code.upper(): d
        for d in (
            await db.execute(select(m.Department).where(m.Department.tenant_id == tenant_id))
        ).scalars().all()
    }
    existing_emails = {
        (e or "").strip().lower()
        for e in (
            await db.execute(select(m.User.email).where(m.User.tenant_id == tenant_id))
        ).scalars().all()
    }

    seen_emails: set[str] = set()
    errors: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    created: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        row_errors: list[str] = []
        full_name = row["full_name"].strip()
        email_raw = row["email"].strip().lower()
        phone = row["phone"].strip() or None
        role_raw = (row["role"] or "cashier").strip().lower() or "cashier"
        branch_code = row["branch_code"].strip().upper()
        department_code = row["department_code"].strip().upper()
        password = row["password"].strip()
        record_scope = row["record_scope"].strip().lower() or None

        if len(full_name) < 2:
            row_errors.append("full_name must be at least 2 characters")
        if not email_raw:
            row_errors.append("email is required")
        else:
            try:
                email_raw = str(_EMAIL.validate_python(email_raw)).lower()
            except ValidationError:
                row_errors.append("invalid email")
        if email_raw in seen_emails:
            row_errors.append("duplicate email in CSV")
        if email_raw in existing_emails:
            row_errors.append("email already exists in tenant")

        role = role_raw
        try:
            role = await roles_svc.assert_assignable_role(
                db, tenant_id, role_raw, actor_role=actor_role
            )
        except HTTPException as exc:
            row_errors.append(str(exc.detail))

        branch_id = None
        department_id = None
        if branch_code:
            branch = branches.get(branch_code)
            if not branch:
                row_errors.append(f"unknown branch_code {branch_code}")
            else:
                branch_id = branch.id
        if department_code:
            department = departments.get(department_code)
            if not department:
                row_errors.append(f"unknown department_code {department_code}")
            else:
                department_id = department.id

        if branch_id or department_id:
            try:
                branch_id, department_id = await org_units_svc.assert_user_org_assignment(
                    db,
                    tenant_id,
                    branch_id=branch_id,
                    department_id=department_id,
                )
            except HTTPException as exc:
                row_errors.append(str(exc.detail))

        if password:
            try:
                validate_password_strength(password)
            except HTTPException as exc:
                row_errors.append(str(exc.detail))
        else:
            password = generate_temp_password()

        scope_value = None
        if record_scope:
            try:
                scope_value = normalize_record_scope(record_scope)
            except ValueError as exc:
                row_errors.append(str(exc))

        if row_errors:
            errors.append({"row": idx, "email": email_raw, "errors": row_errors})
            continue

        seen_emails.add(email_raw)
        preview = {
            "row": idx,
            "full_name": full_name,
            "email": email_raw,
            "phone": phone,
            "role": role,
            "branch_id": branch_id,
            "department_id": department_id,
            "record_scope": scope_value,
            "password_generated": not bool(row["password"].strip()),
        }
        valid_rows.append(preview)

        if dry_run:
            continue

        perms = await roles_svc.permissions_for_assignment(db, tenant_id, role)
        if scope_value is not None:
            perms[RECORD_SCOPE_KEY] = scope_value
        user = m.User(
            tenant_id=tenant_id,
            email=email_raw,
            full_name=full_name,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            branch_id=branch_id,
            department_id=department_id,
            permissions=perms,
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
        created_row = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "password_generated": preview["password_generated"],
        }
        # Temporary passwords only returned outside production (same pattern as verify tokens).
        from app.config import settings

        if settings.DEBUG or settings.APP_ENV.lower() != "production":
            created_row["temporary_password"] = password
            created_row["email_verification_token"] = raw
        created.append(created_row)
        existing_emails.add(email_raw)

    return {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "error_rows": len(errors),
        "errors": errors,
        "preview": valid_rows[:50],
        "created": created,
    }
