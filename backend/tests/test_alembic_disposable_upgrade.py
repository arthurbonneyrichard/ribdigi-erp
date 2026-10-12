"""Apply Alembic upgrade head on a disposable local database.

Never connects to ribdigi_erp, production, or staging. Aborts before any
migration if current_database() is not the disposable name.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

DISPOSABLE_DB = "ribdigi_alembic_head_verify"
FORBIDDEN = {"ribdigi_erp", "production", "staging", "postgres", "template0", "template1"}
LOCAL_HOSTS = {"postgres", "localhost", "127.0.0.1", "::1"}


def _refuse(name: str) -> None:
    folded = (name or "").strip().lower()
    if folded != DISPOSABLE_DB or folded in FORBIDDEN or "production" in folded or "staging" in folded:
        raise SystemExit(f"abort: refusing database {name!r}")


def _file_database_url() -> str:
    """Read the checkout .env. Ignore a process DATABASE_URL left at the dummy port."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        raise SystemExit("abort: checkout .env is missing")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("DATABASE_URL="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("abort: DATABASE_URL is not set in the checkout .env")


def _admin_kwargs() -> dict:
    parsed = urlparse(_file_database_url().replace("postgresql+asyncpg://", "postgresql://"))
    host = (parsed.hostname or "").lower()
    configured = (parsed.path or "").lstrip("/").lower()
    port = parsed.port or 5432
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"abort: refusing non-local database host {host}")
    if port == 9 or configured == "ribdigi_verify_build_graph":
        raise SystemExit("abort: refusing the Alembic graph-check dummy database")
    if configured != "ribdigi_erp":
        raise SystemExit(f"abort: unexpected configured database {configured!r}")
    if not parsed.username or parsed.password is None:
        raise SystemExit("abort: local database credentials are incomplete")
    return {
        "host": "127.0.0.1",
        "port": port,
        "user": parsed.username,
        "password": parsed.password,
        "connect_timeout": 5,
    }


def _login_against_head_schema() -> None:
    """Seed one user on the upgraded disposable database and sign in.

    The caller must already have set DATABASE_URL to ribdigi_alembic_head_verify
    on 127.0.0.1. This function refuses any other database before importing the app.
    """
    import asyncio

    raw = os.environ.get("DATABASE_URL") or ""
    parsed = urlparse(raw.replace("postgresql+asyncpg://", "postgresql://"))
    name = (parsed.path or "").lstrip("/")
    host = (parsed.hostname or "").lower()
    _refuse(name)
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(f"abort: refusing login probe host {host!r}")
    check = psycopg2.connect(
        host=host,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=name,
        connect_timeout=5,
    )
    try:
        with check.cursor() as cur:
            cur.execute("SELECT current_database()")
            current = cur.fetchone()[0]
            if current != DISPOSABLE_DB:
                raise SystemExit(f"abort: current_database() is {current!r}")
            _refuse(current)
    finally:
        check.close()
    asyncio.run(_login_against_head_schema_async(name))


async def _login_against_head_schema_async(database_name: str) -> None:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.db import get_db
    from app.main import app
    from app.models import Tenant, User
    from app.rbac import permissions_for_role
    from app.security import hash_password
    import app.db as db_mod

    if database_name not in (settings.DATABASE_URL or "") or "127.0.0.1" not in (settings.DATABASE_URL or ""):
        raise SystemExit("abort: app settings are not the disposable database")
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            tenant = Tenant(
                slug="head-verify",
                company_name="Head Verify Co",
                status="active",
                industry="retail",
                package_code="professional",
            )
            session.add(tenant)
            await session.flush()
            session.add(
                User(
                    tenant_id=tenant.id,
                    email="head-verify@example.com",
                    full_name="Head Verify",
                    password_hash=hash_password("HeadVerify123!"),
                    role="cashier",
                    email_verified=True,
                    permissions=permissions_for_role("cashier"),
                    totp_enabled=False,
                )
            )
            await session.commit()

        async def override_get_db():
            async with factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        app.state.session_factory = factory
        db_mod.SessionLocal = factory
        settings.RATE_LIMIT_ENABLED = False
        import app.middleware as middleware_mod

        middleware_mod.settings.RATE_LIMIT_ENABLED = False
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            bad = await ac.post(
                "/api/v1/auth/login",
                json={
                    "email": "head-verify@example.com",
                    "password": "WrongPass123!",
                    "tenant_id": "head-verify",
                },
            )
            if bad.status_code != 401:
                raise SystemExit(f"abort: invalid credentials returned {bad.status_code}")
            ok = await ac.post(
                "/api/v1/auth/login",
                json={
                    "email": "head-verify@example.com",
                    "password": "HeadVerify123!",
                    "tenant_id": "head-verify",
                },
            )
            if ok.status_code != 200:
                raise SystemExit(f"abort: valid login returned {ok.status_code}")
            data = (ok.json() or {}).get("data") or {}
            if not data.get("access_token") or not data.get("refresh_token"):
                raise SystemExit("abort: login response did not issue a session")
            if data.get("user", {}).get("email") != "head-verify@example.com":
                raise SystemExit("abort: login response user did not match the seeded account")
        print("disposable_login=ok")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def test_alembic_upgrade_head_on_disposable_database():
    _refuse(DISPOSABLE_DB)
    kwargs = _admin_kwargs()
    admin = psycopg2.connect(dbname="postgres", **kwargs)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            admin_db = cur.fetchone()[0]
            if admin_db != "postgres":
                raise SystemExit(f"abort: admin connection is {admin_db!r}")
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (DISPOSABLE_DB,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {DISPOSABLE_DB}")
            cur.execute(f"CREATE DATABASE {DISPOSABLE_DB}")
    finally:
        admin.close()

    def _drop() -> None:
        _refuse(DISPOSABLE_DB)
        maintenance = psycopg2.connect(dbname="postgres", **kwargs)
        maintenance.autocommit = True
        try:
            with maintenance.cursor() as cur:
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != "postgres":
                    raise SystemExit("abort: refusing to drop from a non-maintenance database")
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (DISPOSABLE_DB,),
                )
                cur.execute(f"DROP DATABASE IF EXISTS {DISPOSABLE_DB}")
        finally:
            maintenance.close()

    try:
        check = psycopg2.connect(dbname=DISPOSABLE_DB, **kwargs)
        try:
            with check.cursor() as cur:
                cur.execute("SELECT current_database()")
                current = cur.fetchone()[0]
                if current != DISPOSABLE_DB:
                    raise SystemExit(f"abort: current_database() is {current!r}")
                _refuse(current)
        finally:
            check.close()

        from urllib.parse import quote

        env = os.environ.copy()
        env["DATABASE_URL"] = (
            "postgresql+asyncpg://"
            f"{quote(kwargs['user'], safe='')}:{quote(kwargs['password'], safe='')}"
            f"@127.0.0.1:{kwargs['port']}/{DISPOSABLE_DB}"
        )
        env["PYTHONPATH"] = "."
        env["APP_ENV"] = "development"
        backend = os.path.join(os.path.dirname(__file__), "..")
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from urllib.parse import urlparse\n"
                    "from app.config import settings\n"
                    "import psycopg2\n"
                    "parsed = urlparse(settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://'))\n"
                    "name = (parsed.path or '').lstrip('/')\n"
                    "host = (parsed.hostname or '').lower()\n"
                    "if name != 'ribdigi_alembic_head_verify' or host not in {'127.0.0.1', 'localhost', '::1'}:\n"
                    "    raise SystemExit('abort: alembic settings would not use the disposable database')\n"
                    "conn = psycopg2.connect(host=host, port=parsed.port or 5432, user=parsed.username, password=parsed.password, dbname=name, connect_timeout=5)\n"
                    "cur = conn.cursor()\n"
                    "cur.execute('SELECT current_database()')\n"
                    "current = cur.fetchone()[0]\n"
                    "conn.close()\n"
                    "if current != 'ribdigi_alembic_head_verify':\n"
                    "    raise SystemExit('abort: current_database() is not disposable')\n"
                    "print(current)\n"
                ),
            ],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0 or probe.stdout.strip() != DISPOSABLE_DB:
            detail = ((probe.stderr or "") + "\n" + (probe.stdout or "")).replace(str(kwargs["password"]), "***")
            pytest.fail(detail[-2000:] or "disposable database probe failed")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or "") + "\n" + (result.stdout or "")
            detail = detail.replace(str(kwargs["password"]), "***")
            pytest.fail(detail[-2000:] or "alembic upgrade head failed")

        verify = psycopg2.connect(dbname=DISPOSABLE_DB, **kwargs)
        try:
            with verify.cursor() as cur:
                cur.execute("SELECT current_database()")
                current = cur.fetchone()[0]
                if current != DISPOSABLE_DB:
                    raise SystemExit(f"abort: current_database() is {current!r}")
                _refuse(current)
                cur.execute("SELECT version_num FROM alembic_version")
                versions = [row[0] for row in cur.fetchall()]
                assert versions == ["20261008_0136"]
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'auth_sessions'"
                )
                columns = {row[0] for row in cur.fetchall()}
                for required in ("id", "tenant_id", "user_id", "refresh_token_hash", "jti", "expires_at"):
                    assert required in columns
        finally:
            verify.close()

        env["RATE_LIMIT_ENABLED"] = "false"
        env["LOGIN_2FA_ENABLED"] = "false"
        login = subprocess.run(
            [sys.executable, "-c", "from tests.test_alembic_disposable_upgrade import _login_against_head_schema; _login_against_head_schema()"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
        )
        if login.returncode != 0:
            detail = ((login.stderr or "") + "\n" + (login.stdout or "")).replace(str(kwargs["password"]), "***")
            pytest.fail(detail[-2000:] or "login against upgrade head failed")
    finally:
        _drop()
