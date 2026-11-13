"""Live server (VPS) health and performance for the software owner.

One reading ("snapshot") covers the machine (CPU, memory, disk, load), the API
process, request speed, the databases, Redis, the job workers, backups and the
public web address with its TLS certificate. Readings are kept in Redis (one a
minute, seven days) so the owner sees history and uptime; without Redis they are
kept in this process only.

Alerts: a check that goes critical raises a ``server_health`` notification for
platform staff (in-app + email by their preferences), at most once per cooldown,
and a "recovered" note when it is back to normal.

Nothing here returns secrets, connection strings or file paths of tenant data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import ssl
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics as metrics_svc
from app.config import settings

logger = logging.getLogger("ribdigi.monitor")

SAMPLES_KEY = "ribdigi:monitor:samples"
EVENTS_KEY = "ribdigi:monitor:events"
ACTIVE_KEY = "ribdigi:monitor:active"
JOB_BEAT_KEY = "ribdigi:monitor:last_job_sample"
MAX_SAMPLES = 7 * 24 * 60
MAX_EVENTS = 200
SAMPLE_MIN_GAP_SECONDS = 55
JOB_STALE_SECONDS = 5 * 60

# In-process fallbacks when Redis is not available.
_mem_samples: deque[dict] = deque(maxlen=MAX_SAMPLES)
_mem_events: deque[dict] = deque(maxlen=MAX_EVENTS)
_mem_active: dict[str, dict] = {}
_mem_cooldown: dict[str, float] = {}
_mem_job_beat: float = 0.0
_cache: dict[str, tuple[float, Any]] = {}
_last_cpu_times: tuple[float, float] | None = None

STATUS_ORDER = {"ok": 0, "warn": 1, "critical": 2, "unknown": 0}


def reset_for_tests() -> None:
    global _mem_job_beat, _last_cpu_times
    _mem_samples.clear()
    _mem_events.clear()
    _mem_active.clear()
    _mem_cooldown.clear()
    _cache.clear()
    _mem_job_beat = 0.0
    _last_cpu_times = None


def _now() -> float:
    return time.time()


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _pct(used: float, total: float) -> float:
    return round(used / total * 100.0, 1) if total else 0.0


# ---------------------------------------------------------------- Redis access


def _redis_url() -> str:
    return (settings.REDIS_URL or "").strip()


async def _redis():
    url = _redis_url()
    if not url or os.environ.get("RIBDIGI_MONITOR_NO_REDIS"):
        return None
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.5,
        )
        await client.ping()
        return client
    except Exception:
        return None


async def _close(client) -> None:
    if client is not None:
        try:
            await client.aclose()
        except Exception:
            pass


# ------------------------------------------------------------------ the machine


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _proc_cpu_times() -> tuple[float, float] | None:
    raw = _read("/proc/stat")
    if not raw:
        return None
    parts = raw.splitlines()[0].split()[1:]
    vals = [float(x) for x in parts]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0.0)
    return sum(vals), idle


def _cpu_percent_sync() -> float | None:
    """CPU busy % over a short window (psutil when present, else /proc/stat)."""
    global _last_cpu_times
    try:
        import psutil

        return float(psutil.cpu_percent(interval=0.3))
    except Exception:
        pass
    first = _proc_cpu_times()
    if first is None:
        return None
    time.sleep(0.3)
    second = _proc_cpu_times()
    if second is None:
        return None
    total = second[0] - first[0]
    idle = second[1] - first[1]
    _last_cpu_times = second
    return round((1.0 - idle / total) * 100.0, 1) if total > 0 else 0.0


def _memory_sync() -> dict[str, Any]:
    try:
        import psutil

        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {
            "total_bytes": int(vm.total),
            "used_bytes": int(vm.total - vm.available),
            "available_bytes": int(vm.available),
            "used_pct": _pct(vm.total - vm.available, vm.total),
            "swap_total_bytes": int(sw.total),
            "swap_used_bytes": int(sw.used),
            "swap_used_pct": _pct(sw.used, sw.total),
        }
    except Exception:
        pass
    raw = _read("/proc/meminfo")
    if not raw:
        return {}
    info: dict[str, int] = {}
    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        num = rest.strip().split(" ")[0]
        if num.isdigit():
            info[key] = int(num) * 1024
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    sw_total = info.get("SwapTotal", 0)
    sw_used = sw_total - info.get("SwapFree", 0)
    return {
        "total_bytes": total,
        "used_bytes": total - avail,
        "available_bytes": avail,
        "used_pct": _pct(total - avail, total),
        "swap_total_bytes": sw_total,
        "swap_used_bytes": sw_used,
        "swap_used_pct": _pct(sw_used, sw_total),
    }


def _container_memory() -> dict[str, Any] | None:
    """cgroup memory limit when the API runs in a container with a cap."""
    limit = (_read("/sys/fs/cgroup/memory.max") or "").strip()
    current = (_read("/sys/fs/cgroup/memory.current") or "").strip()
    if not limit:
        limit = (_read("/sys/fs/cgroup/memory/memory.limit_in_bytes") or "").strip()
        current = (_read("/sys/fs/cgroup/memory/memory.usage_in_bytes") or "").strip()
    if not limit.isdigit() or not current.isdigit():
        return None
    lim, cur = int(limit), int(current)
    if lim <= 0 or lim > (1 << 60):
        return None
    return {"limit_bytes": lim, "used_bytes": cur, "used_pct": _pct(cur, lim)}


def _disks_sync() -> list[dict[str, Any]]:
    targets = [("System disk", os.path.abspath(os.sep))]
    for label, path in (("Backups", settings.BACKUP_DIR), ("Uploaded files", settings.MEDIA_DIR)):
        if path and os.path.isdir(path):
            targets.append((label, path))
    seen: set[tuple[int, int]] = set()
    out: list[dict[str, Any]] = []
    for label, path in targets:
        try:
            usage = shutil.disk_usage(path)
        except Exception:
            continue
        key = (usage.total, usage.used // (1 << 20))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "label": label,
                "total_bytes": int(usage.total),
                "used_bytes": int(usage.used),
                "free_bytes": int(usage.free),
                "used_pct": _pct(usage.used, usage.total),
            }
        )
    return out


def _uptime_seconds() -> float | None:
    raw = _read("/proc/uptime")
    if raw:
        try:
            return float(raw.split()[0])
        except Exception:
            return None
    try:
        import psutil

        return max(0.0, _now() - float(psutil.boot_time()))
    except Exception:
        return None


def _process_sync() -> dict[str, Any]:
    out: dict[str, Any] = {
        "pid": os.getpid(),
        "started_at": _iso(metrics_svc.process_started_at()),
        "uptime_seconds": round(_now() - metrics_svc.process_started_at(), 0),
        "python": platform.python_version(),
    }
    try:
        import psutil

        proc = psutil.Process()
        out["rss_bytes"] = int(proc.memory_info().rss)
        out["threads"] = int(proc.num_threads())
        try:
            out["open_files"] = int(proc.num_fds())
        except Exception:
            pass
        return out
    except Exception:
        pass
    raw = _read("/proc/self/status")
    if raw:
        for line in raw.splitlines():
            if line.startswith("VmRSS:"):
                out["rss_bytes"] = int(line.split()[1]) * 1024
            elif line.startswith("Threads:"):
                out["threads"] = int(line.split()[1])
    try:
        out["open_files"] = len(os.listdir("/proc/self/fd"))
    except Exception:
        pass
    return out


def host_stats_sync() -> dict[str, Any]:
    cores = os.cpu_count() or 1
    load: list[float] | None = None
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        load = None
    return {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "in_container": os.path.exists("/.dockerenv"),
        "cpu_cores": cores,
        "cpu_pct": _cpu_percent_sync(),
        "load_avg": load,
        "load_per_core": round(load[0] / cores, 2) if load else None,
        "memory": _memory_sync(),
        "container_memory": _container_memory(),
        "disks": _disks_sync(),
        "uptime_seconds": _uptime_seconds(),
    }


# ----------------------------------------------------------- services checked


async def _database_stats(db: AsyncSession) -> dict[str, Any]:
    start = time.perf_counter()
    out: dict[str, Any] = {}
    try:
        await db.execute(text("SELECT 1"))
        out["latency_ms"] = round((time.perf_counter() - start) * 1000.0, 1)
        out["status"] = "ok"
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    dialect = db.bind.dialect.name if db.bind is not None else ""
    out["engine"] = dialect
    try:
        if dialect == "postgresql":
            row = (
                await db.execute(
                    text(
                        """
                        SELECT pg_database_size(current_database()) AS size,
                               (SELECT count(*) FROM pg_stat_activity
                                 WHERE datname = current_database()) AS conns,
                               (SELECT count(*) FROM pg_stat_activity
                                 WHERE datname = current_database() AND state = 'active') AS active,
                               (SELECT count(*) FROM pg_stat_activity
                                 WHERE datname = current_database() AND state = 'active'
                                   AND now() - query_start > interval '30 seconds') AS slow,
                               current_setting('max_connections')::int AS max_conns
                        """
                    )
                )
            ).mappings().first()
            if row:
                out.update(
                    {
                        "size_bytes": int(row["size"] or 0),
                        "connections": int(row["conns"] or 0),
                        "active_queries": int(row["active"] or 0),
                        "slow_queries": int(row["slow"] or 0),
                        "max_connections": int(row["max_conns"] or 0),
                    }
                )
                out["connections_pct"] = _pct(out["connections"], out["max_connections"])
        elif dialect == "sqlite":
            path = (settings.DATABASE_URL or "").split("///", 1)[-1]
            if path and os.path.isfile(path):
                out["size_bytes"] = os.path.getsize(path)
    except Exception:
        logger.debug("database detail query failed", exc_info=True)
    try:
        from app.db import engine

        pool = engine.sync_engine.pool
        out["pool"] = {
            "size": int(pool.size()) if hasattr(pool, "size") else None,
            "checked_out": int(pool.checkedout()) if hasattr(pool, "checkedout") else None,
            "overflow": int(pool.overflow()) if hasattr(pool, "overflow") else None,
        }
    except Exception:
        pass
    return out


async def _desk_databases() -> list[dict[str, Any]]:
    """Latency of each desk's own database (hotel, restaurant, ...)."""
    try:
        from app.db import engine_for
        from app.desks import desk_urls
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for desk, url in sorted(desk_urls().items()):
        if not url or url == settings.DATABASE_URL:
            continue
        start = time.perf_counter()
        try:
            async with engine_for(desk).connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=3.0)
            out.append(
                {"desk": desk, "status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000.0, 1)}
            )
        except Exception as exc:
            out.append({"desk": desk, "status": "error", "error": type(exc).__name__})
    return out


async def _redis_stats() -> dict[str, Any]:
    if not _redis_url():
        return {"status": "skipped", "reason": "Redis is not configured"}
    start = time.perf_counter()
    client = await _redis()
    if client is None:
        return {"status": "error", "error": "unreachable"}
    try:
        info = await client.info()
        latency = round((time.perf_counter() - start) * 1000.0, 1)
        used = int(info.get("used_memory") or 0)
        maxmem = int(info.get("maxmemory") or 0)
        return {
            "status": "ok",
            "latency_ms": latency,
            "version": info.get("redis_version"),
            "used_memory_bytes": used,
            "max_memory_bytes": maxmem or None,
            "used_memory_pct": _pct(used, maxmem) if maxmem else None,
            "clients": int(info.get("connected_clients") or 0),
            "uptime_seconds": int(info.get("uptime_in_seconds") or 0),
        }
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    finally:
        await _close(client)


def _ping_workers_sync() -> list[str]:
    from app.celery_app import celery

    replies = celery.control.ping(timeout=1.0) or []
    names: list[str] = []
    for reply in replies:
        names.extend(reply.keys())
    return sorted(names)


async def _worker_stats() -> dict[str, Any]:
    beat_ts = await last_job_sample_at()
    out: dict[str, Any] = {
        "enabled": bool(settings.CELERY_ENABLED),
        "last_scheduled_run_at": _iso(beat_ts),
        "scheduled_jobs_stale": bool(
            settings.CELERY_ENABLED and not settings.CELERY_TASK_ALWAYS_EAGER
            and (not beat_ts or _now() - beat_ts > JOB_STALE_SECONDS)
        ),
    }
    if not settings.CELERY_ENABLED:
        out["status"] = "skipped"
        return out
    if settings.CELERY_TASK_ALWAYS_EAGER:
        out["status"] = "ok"
        out["mode"] = "eager"
        out["scheduled_jobs_stale"] = False
        return out
    try:
        names = await asyncio.wait_for(asyncio.to_thread(_ping_workers_sync), timeout=3.0)
        out["workers"] = len(names)
        out["status"] = "ok" if names else "error"
    except Exception as exc:
        out["workers"] = 0
        out["status"] = "error"
        out["error"] = type(exc).__name__
    return out


async def _backup_stats(db: AsyncSession) -> dict[str, Any]:
    from app import models as m

    try:
        last_ok = (
            await db.execute(
                select(func.max(m.BackupJob.created_at)).where(m.BackupJob.status == "completed")
            )
        ).scalar()
        since = datetime.utcnow() - timedelta(hours=24)
        failed = (
            await db.execute(
                select(func.count())
                .select_from(m.BackupJob)
                .where(m.BackupJob.status == "failed", m.BackupJob.created_at >= since)
            )
        ).scalar() or 0
        scheduled = (
            await db.execute(
                select(func.count())
                .select_from(m.BackupSettings)
                .where(m.BackupSettings.enabled == True)  # noqa: E712
            )
        ).scalar() or 0
        last_failure = (
            await db.execute(
                select(m.BackupJob.error_message, m.BackupJob.created_at)
                .where(m.BackupJob.status == "failed")
                .order_by(m.BackupJob.created_at.desc())
                .limit(1)
            )
        ).first()
    except Exception as exc:
        return {"status": "unknown", "error": type(exc).__name__}
    from app import backup as backup_svc

    try:
        backup_svc.ensure_backup_dir_writable()
        writable = True
    except Exception:  # noqa: BLE001
        writable = False
    age_h = None
    if last_ok:
        age_h = round((datetime.utcnow() - last_ok).total_seconds() / 3600.0, 1)
    return {
        "last_success_at": last_ok.replace(tzinfo=timezone.utc).isoformat() if last_ok else None,
        "age_hours": age_h,
        "failed_last_24h": int(failed),
        "companies_scheduled": int(scheduled),
        "dir_writable": writable,
        "last_error": (last_failure[0] or "")[:300] if last_failure else None,
        "last_error_at": last_failure[1].replace(tzinfo=timezone.utc).isoformat() if last_failure and last_failure[1] else None,
    }


def _public_url() -> str:
    return (settings.MONITOR_PUBLIC_URL or settings.FRONTEND_URL or "").strip().rstrip("/")


async def _web_check() -> dict[str, Any]:
    url = _public_url()
    if not url:
        return {"status": "skipped", "reason": "No public address set"}
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"} and os.path.exists("/.dockerenv"):
        # Inside a container, localhost is the container itself, not the website.
        return {"status": "skipped", "url": url, "reason": "Local address; set MONITOR_PUBLIC_URL"}
    cached = _cache.get("web")
    if cached and _now() - cached[0] < 60:
        return cached[1]
    start = time.perf_counter()
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(url)
        result = {
            "url": url,
            "status": "ok" if resp.status_code < 500 else "error",
            "http_status": resp.status_code,
            "latency_ms": round((time.perf_counter() - start) * 1000.0, 1),
        }
    except Exception as exc:
        result = {"url": url, "status": "error", "error": type(exc).__name__}
    _cache["web"] = (_now(), result)
    return result


def _cert_days_sync(host: str, port: int) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=4.0) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    issuer = dict(x[0] for x in cert.get("issuer", ()))
    return {
        "status": "ok",
        "host": host,
        "expires_at": not_after.isoformat(),
        "days_left": int((not_after - datetime.now(timezone.utc)).total_seconds() // 86400),
        "issuer": issuer.get("organizationName") or issuer.get("commonName"),
    }


async def _tls_check() -> dict[str, Any]:
    url = _public_url()
    parsed = urlparse(url) if url else None
    if not parsed or parsed.scheme != "https" or not parsed.hostname:
        return {"status": "skipped", "reason": "Public address is not https"}
    cached = _cache.get("tls")
    if cached and _now() - cached[0] < 6 * 3600:
        return cached[1]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_cert_days_sync, parsed.hostname, parsed.port or 443), timeout=6.0
        )
    except Exception as exc:
        result = {"status": "error", "host": parsed.hostname, "error": type(exc).__name__}
    _cache["tls"] = (_now(), result)
    return result


# ------------------------------------------------------------------- checks


def _check(key: str, label: str, status: str, value: str, detail: str = "") -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "value": value, "detail": detail}


def _level(value: float | None, limit: float, warn_ratio: float = 0.85) -> str:
    if value is None:
        return "unknown"
    if value >= limit:
        return "critical"
    if value >= limit * warn_ratio:
        return "warn"
    return "ok"


def build_checks(snap: dict[str, Any]) -> list[dict[str, str]]:
    host = snap.get("host") or {}
    checks: list[dict[str, str]] = []
    cpu = host.get("cpu_pct")
    checks.append(
        _check("cpu", "Processor", _level(cpu, settings.MONITOR_CPU_ALERT_PCT),
               f"{cpu:.0f}%" if cpu is not None else "n/a",
               f"Alert at {settings.MONITOR_CPU_ALERT_PCT:.0f}%")
    )
    mem = (host.get("memory") or {}).get("used_pct")
    checks.append(
        _check("memory", "Memory", _level(mem, settings.MONITOR_MEMORY_ALERT_PCT),
               f"{mem:.0f}%" if mem is not None else "n/a",
               f"Alert at {settings.MONITOR_MEMORY_ALERT_PCT:.0f}%")
    )
    disks = host.get("disks") or []
    worst = max(disks, key=lambda d: d["used_pct"]) if disks else None
    checks.append(
        _check("disk", "Disk space", _level(worst["used_pct"] if worst else None, settings.MONITOR_DISK_ALERT_PCT, 0.9),
               f"{worst['used_pct']:.0f}% used" if worst else "n/a",
               f"{worst['label']}; alert at {settings.MONITOR_DISK_ALERT_PCT:.0f}%" if worst else "")
    )
    db = snap.get("database") or {}
    if db.get("status") == "error":
        checks.append(_check("database", "Main database", "critical", "down", db.get("error") or ""))
    else:
        lat = db.get("latency_ms")
        checks.append(
            _check("database", "Main database", _level(lat, settings.MONITOR_DB_LATENCY_ALERT_MS, 0.5),
                   f"{lat:.0f} ms" if lat is not None else "n/a", "Reply time to a simple query")
        )
    for desk in snap.get("desk_databases") or []:
        checks.append(
            _check(f"desk_db:{desk['desk']}", f"{desk['desk'].title()} database",
                   "ok" if desk["status"] == "ok" else "critical",
                   f"{desk.get('latency_ms', 0):.0f} ms" if desk["status"] == "ok" else "down")
        )
    redis = snap.get("redis") or {}
    if redis.get("status") != "skipped":
        checks.append(
            _check("redis", "Redis (cache, limits)", "ok" if redis.get("status") == "ok" else "critical",
                   f"{redis.get('latency_ms', 0):.0f} ms" if redis.get("status") == "ok" else "down")
        )
    workers = snap.get("workers") or {}
    if workers.get("status") not in (None, "skipped"):
        if workers.get("status") == "error":
            checks.append(_check("workers", "Background workers", "critical", "not answering",
                                 "Emails, backups and renewals wait until a worker is back"))
        else:
            n = workers.get("workers")
            checks.append(_check("workers", "Background workers", "ok",
                                 f"{n} running" if n is not None else workers.get("mode") or "ok"))
        if workers.get("scheduled_jobs_stale") and snap.get("source") == "api":
            if workers.get("last_scheduled_run_at"):
                checks.append(_check("scheduler", "Scheduled jobs", "critical", "stopped",
                                     "No scheduled run in the last 5 minutes (celery beat)"))
            else:
                checks.append(_check("scheduler", "Scheduled jobs", "warn", "waiting",
                                     "No scheduled reading seen yet; restart celery_worker and celery_beat after updating"))
    perf = snap.get("performance") or {}
    if perf.get("requests", 0) >= 20:
        p95 = perf.get("p95_ms")
        checks.append(_check("latency", "Response time (p95)", _level(p95, settings.MONITOR_P95_ALERT_MS, 0.5),
                             f"{p95:.0f} ms", "Slowest 5% of requests, last 15 minutes"))
        err = perf.get("error_rate_pct")
        checks.append(_check("errors", "Server errors", _level(err, settings.MONITOR_ERROR_RATE_ALERT_PCT, 0.4),
                             f"{err:.1f}%", f"{perf.get('server_errors', 0)} of {perf.get('requests', 0)} requests"))
    backups = snap.get("backups") or {}
    if backups.get("companies_scheduled"):
        age = backups.get("age_hours")
        status = "critical" if age is None or age > settings.MONITOR_BACKUP_MAX_AGE_HOURS else "ok"
        if status == "ok" and backups.get("failed_last_24h"):
            status = "warn"
        checks.append(_check("backups", "Backups", status,
                             f"{age:.0f} h ago" if age is not None else "none yet",
                             f"{backups.get('failed_last_24h', 0)} failed in 24 h"))
    web = snap.get("web") or {}
    if web.get("status") != "skipped":
        checks.append(_check("web", "Public website", "ok" if web.get("status") == "ok" else "critical",
                             f"{web.get('latency_ms', 0):.0f} ms" if web.get("status") == "ok"
                             else str(web.get("http_status") or "unreachable"), web.get("url") or ""))
    tls = snap.get("tls") or {}
    if tls.get("status") == "ok":
        days = tls["days_left"]
        limit = settings.MONITOR_CERT_ALERT_DAYS
        checks.append(_check("tls", "Security certificate",
                             "critical" if days <= limit // 2 else ("warn" if days <= limit else "ok"),
                             f"{days} days left", tls.get("issuer") or ""))
    elif tls.get("status") == "error":
        checks.append(_check("tls", "Security certificate", "critical", "cannot read", tls.get("error") or ""))
    return checks


def overall_status(checks: list[dict[str, str]]) -> str:
    worst = 0
    for c in checks:
        worst = max(worst, STATUS_ORDER.get(c["status"], 0))
    return {0: "ok", 1: "warn", 2: "critical"}[worst]


async def collect_snapshot(db: AsyncSession, *, source: str = "api") -> dict[str, Any]:
    host_task = asyncio.to_thread(host_stats_sync)
    host, redis, workers, web, tls, desks = await asyncio.gather(
        host_task, _redis_stats(), _worker_stats(), _web_check(), _tls_check(), _desk_databases()
    )
    snap: dict[str, Any] = {
        "at": _iso(_now()),
        "source": source,
        "environment": settings.APP_ENV,
        "release_channel": settings.RIBDIGI_RELEASE_CHANNEL,
        "build_id": settings.RIBDIGI_BUILD_ID,
        "host": host,
        "process": await asyncio.to_thread(_process_sync),
        "performance": metrics_svc.recent_performance(900) if source == "api" else None,
        "database": await _database_stats(db),
        "desk_databases": desks,
        "redis": redis,
        "workers": workers,
        "backups": await _backup_stats(db),
        "web": web,
        "tls": tls,
    }
    snap["checks"] = build_checks(snap)
    snap["status"] = overall_status(snap["checks"])
    return snap


# ------------------------------------------------------------ history store


def compact(snap: dict[str, Any]) -> dict[str, Any]:
    host = snap.get("host") or {}
    disks = host.get("disks") or []
    perf = snap.get("performance") or {}
    return {
        "t": round(_now(), 0),
        "s": snap.get("status"),
        "cpu": host.get("cpu_pct"),
        "mem": (host.get("memory") or {}).get("used_pct"),
        "disk": max((d["used_pct"] for d in disks), default=None),
        "load": (host.get("load_avg") or [None])[0],
        "db": (snap.get("database") or {}).get("latency_ms"),
        "redis": (snap.get("redis") or {}).get("latency_ms"),
        "web": (snap.get("web") or {}).get("latency_ms"),
        "p95": perf.get("p95_ms") if perf.get("requests") else None,
        "rpm": perf.get("requests_per_minute") if perf else None,
        "err": perf.get("error_rate_pct") if perf.get("requests") else None,
        "src": snap.get("source"),
    }


async def store_sample(point: dict[str, Any]) -> None:
    client = await _redis()
    if client is None:
        _mem_samples.append(point)
        return
    try:
        await client.rpush(SAMPLES_KEY, json.dumps(point))
        await client.ltrim(SAMPLES_KEY, -MAX_SAMPLES, -1)
    except Exception:
        _mem_samples.append(point)
    finally:
        await _close(client)


async def load_samples(since_seconds: int) -> list[dict[str, Any]]:
    cutoff = _now() - since_seconds
    client = await _redis()
    rows: list[dict[str, Any]] = []
    if client is not None:
        try:
            # Newest last; one point a minute, so read just enough from the tail.
            count = min(MAX_SAMPLES, int(since_seconds / 60) * 3 + 10)
            for raw in await client.lrange(SAMPLES_KEY, -count, -1):
                try:
                    rows.append(json.loads(raw))
                except Exception:
                    continue
        except Exception:
            rows = []
        finally:
            await _close(client)
    if not rows:
        rows = list(_mem_samples)
    return [r for r in rows if (r.get("t") or 0) >= cutoff]


async def latest_sample_at() -> float:
    rows = await load_samples(10 * 60)
    return max((r.get("t") or 0 for r in rows), default=0.0)


async def mark_job_sample() -> None:
    global _mem_job_beat
    _mem_job_beat = _now()
    client = await _redis()
    if client is None:
        return
    try:
        await client.set(JOB_BEAT_KEY, str(_mem_job_beat), ex=24 * 3600)
    except Exception:
        pass
    finally:
        await _close(client)


async def last_job_sample_at() -> float:
    client = await _redis()
    if client is None:
        return _mem_job_beat
    try:
        raw = await client.get(JOB_BEAT_KEY)
        return float(raw) if raw else _mem_job_beat
    except Exception:
        return _mem_job_beat
    finally:
        await _close(client)


METRIC_KEYS = ("cpu", "mem", "disk", "load", "db", "redis", "web", "p95", "rpm", "err")


def downsample(rows: list[dict[str, Any]], buckets: int, since_seconds: int) -> list[dict[str, Any]]:
    """Average readings into at most ``buckets`` time buckets (worst status wins)."""
    if not rows:
        return []
    end = _now()
    start = end - since_seconds
    width = max(60.0, since_seconds / max(1, buckets))
    grouped: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        idx = int(((r.get("t") or start) - start) // width)
        grouped.setdefault(idx, []).append(r)
    out: list[dict[str, Any]] = []
    for idx in sorted(grouped):
        group = grouped[idx]
        point: dict[str, Any] = {"t": _iso(start + idx * width + width / 2)}
        for key in METRIC_KEYS:
            vals = [g[key] for g in group if isinstance(g.get(key), (int, float))]
            point[key] = round(sum(vals) / len(vals), 2) if vals else None
        point["s"] = {0: "ok", 1: "warn", 2: "critical"}[
            max(STATUS_ORDER.get(g.get("s") or "ok", 0) for g in group)
        ]
        out.append(point)
    return out


def uptime_from(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"samples": 0, "healthy_pct": None, "web_up_pct": None}
    healthy = sum(1 for r in rows if r.get("s") != "critical")
    web_rows = [r for r in rows if "web" in r]
    web_up = sum(1 for r in web_rows if r.get("web") is not None)
    return {
        "samples": len(rows),
        "healthy_pct": round(healthy / len(rows) * 100.0, 2),
        "web_up_pct": round(web_up / len(web_rows) * 100.0, 2) if web_rows and _public_url() else None,
    }


# ------------------------------------------------------------------ alerts


async def _push_event(event: dict[str, Any]) -> None:
    client = await _redis()
    if client is None:
        _mem_events.appendleft(event)
        return
    try:
        await client.lpush(EVENTS_KEY, json.dumps(event))
        await client.ltrim(EVENTS_KEY, 0, MAX_EVENTS - 1)
    except Exception:
        _mem_events.appendleft(event)
    finally:
        await _close(client)


async def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    client = await _redis()
    if client is not None:
        try:
            raw = await client.lrange(EVENTS_KEY, 0, limit - 1)
            return [json.loads(x) for x in raw]
        except Exception:
            pass
        finally:
            await _close(client)
    return list(_mem_events)[:limit]


async def active_alerts() -> dict[str, dict]:
    client = await _redis()
    if client is not None:
        try:
            raw = await client.hgetall(ACTIVE_KEY)
            return {k: json.loads(v) for k, v in raw.items()}
        except Exception:
            pass
        finally:
            await _close(client)
    return dict(_mem_active)


async def _set_active(key: str, value: dict | None) -> None:
    client = await _redis()
    if client is None:
        if value is None:
            _mem_active.pop(key, None)
        else:
            _mem_active[key] = value
        return
    try:
        if value is None:
            await client.hdel(ACTIVE_KEY, key)
        else:
            await client.hset(ACTIVE_KEY, key, json.dumps(value))
    except Exception:
        pass
    finally:
        await _close(client)


async def _cooldown_ok(key: str) -> bool:
    """True when this alert may be sent now (claims the cooldown slot)."""
    seconds = max(60, int(settings.MONITOR_ALERT_COOLDOWN_MINUTES) * 60)
    client = await _redis()
    if client is None:
        last = _mem_cooldown.get(key, 0.0)
        if _now() - last < seconds:
            return False
        _mem_cooldown[key] = _now()
        return True
    try:
        return bool(await client.set(f"ribdigi:monitor:cooldown:{key}", "1", nx=True, ex=seconds))
    except Exception:
        return True
    finally:
        await _close(client)


async def platform_tenant_id(db: AsyncSession) -> str | None:
    from app import models as m
    from app.tenants import PROTECTED_TENANT_SLUGS

    row = (
        await db.execute(
            select(m.Tenant.id).where(m.Tenant.slug.in_(sorted(PROTECTED_TENANT_SLUGS))).limit(1)
        )
    ).scalar()
    if row:
        return row
    # Older installs: the owner's workspace is wherever the platform staff sit.
    from app.rbac import PLATFORM_ROLES

    return (
        await db.execute(
            select(m.User.tenant_id)
            .where(m.User.role.in_(sorted(PLATFORM_ROLES)), m.User.is_active == True)  # noqa: E712
            .limit(1)
        )
    ).scalar()


async def _notify(db: AsyncSession, title: str, message: str) -> bool:
    from app import notifications as notifications_svc

    tenant_id = await platform_tenant_id(db)
    if not tenant_id:
        return False
    note = await notifications_svc.notify_platform_event(
        db,
        tenant_id=tenant_id,
        category="server_health",
        title=title,
        message=message,
        entity_type="server",
        # The plain-language alert email is sent by _email_staff, once per check-up.
        send_email=False,
    )
    return note is not None


async def alert_recipients(db: AsyncSession) -> list[str]:
    """Emails of active platform staff who keep server-health email switched on."""
    from app import notifications as notifications_svc
    from app.rbac import PLATFORM_ROLES

    tenant_id = await platform_tenant_id(db)
    if not tenant_id:
        return []
    out: set[str] = set()
    for user in await notifications_svc.users_for_roles(db, tenant_id, sorted(PLATFORM_ROLES)):
        if user.email and await notifications_svc.channel_enabled(
            db, tenant_id=tenant_id, user_id=user.id, category="server_health", channel="email"
        ):
            out.add(user.email)
    return sorted(out)


async def _email_staff(db: AsyncSession, built: tuple[str, str, str]) -> int:
    """Send one branded alert email to each platform staff member. Returns how many went."""
    from app import emailer

    subject, text, inner = built
    try:
        from app.email_design import refresh_platform_style

        await refresh_platform_style()
    except Exception:
        pass
    html_body = emailer.render_branded_html(
        body_html=inner, tenant=None, title=subject, preheader=text.split("\n", 1)[0]
    )
    sent = 0
    for to in await alert_recipients(db):
        try:
            await emailer.send_email(to=to, subject=subject, text_body=text, html_body=html_body)
            sent += 1
        except Exception:
            logger.exception("server alert email failed")
    return sent


async def evaluate_alerts(db: AsyncSession, snap: dict[str, Any]) -> list[dict[str, Any]]:
    """Raise alerts for critical checks and resolved notes for cleared ones.

    All changes in one check-up go out as one problems email and one resolved
    email, so a bad minute never floods the inbox.
    """
    from app import server_alert_email as mail

    fired: list[dict[str, Any]] = []
    new_problems: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    active = await active_alerts()
    current = {c["key"]: c for c in snap.get("checks") or []}
    host = (snap.get("host") or {}).get("hostname") or "server"
    for key, check in current.items():
        if check["status"] != "critical":
            continue
        since = (active.get(key) or {}).get("since") or snap.get("at")
        if key not in active:
            await _set_active(key, {"since": since, "label": check["label"]})
        if not await _cooldown_ok(key):
            continue
        info = mail.help_for(key)
        event = {"at": snap.get("at"), "kind": "alert", "key": key, "label": check["label"],
                 "value": check["value"], "detail": check["detail"], "since": since}
        await _push_event(event)
        await _notify(
            db,
            f"Action needed: {check['label']} is {check['value']}",
            f"{check['label']} on {host} is {check['value']} (alert limit {mail.limit_for(key)}). "
            f"{info['means']} First step: {info['do'][0]}",
        )
        new_problems.append(event)
        fired.append(event)
    for key, info in active.items():
        check = current.get(key)
        if check is not None and check["status"] == "critical":
            continue
        if check is None and snap.get("source") != "api" and key in {"latency", "errors", "scheduler"}:
            # The worker cannot see API request speed; leave those to the API reading.
            continue
        await _set_active(key, None)
        label = info.get("label") or key
        event = {"at": snap.get("at"), "kind": "recovered", "key": key, "label": label,
                 "value": check["value"] if check else "ok", "detail": f"Since {info.get('since')}",
                 "since": info.get("since")}
        await _push_event(event)
        await _notify(db, f"Resolved: {label} is back to normal", f"{label} is back to normal on {host}. Nothing more to do.")
        resolved.append(event)
        fired.append(event)
    if new_problems:
        await _email_staff(db, mail.build_alert_email(new_problems, host))
    if resolved:
        await _email_staff(db, mail.build_recovered_email(resolved, host))
    return fired


async def record(db: AsyncSession, *, source: str, force: bool = False) -> dict[str, Any]:
    """Take a reading, store it (unless one is fresh) and evaluate alerts."""
    snap = await collect_snapshot(db, source=source)
    if not settings.MONITOR_ENABLED:
        return snap
    if source == "worker":
        await mark_job_sample()
    if force or source == "worker" or _now() - await latest_sample_at() >= SAMPLE_MIN_GAP_SECONDS:
        await store_sample(compact(snap))
        try:
            await evaluate_alerts(db, snap)
            await db.commit()
        except Exception:
            logger.exception("server monitor alert evaluation failed")
            await db.rollback()
    return snap


async def send_test_alert(db: AsyncSession, *, by: str) -> dict[str, Any]:
    from app import server_alert_email as mail

    event = {"at": _iso(_now()), "kind": "test", "key": "test", "label": "Test alert",
             "value": "sent", "detail": f"Sent by {by}"}
    await _push_event(event)
    ok = await _notify(
        db,
        "Test: server alerts are working",
        "This is a test from Server health. Nothing is wrong. Real alerts say what is wrong, "
        "the reading against its limit, and what to do.",
    )
    emailed = await _email_staff(db, mail.build_test_email(by, socket.gethostname()))
    await db.commit()
    return {"delivered": ok, "emailed": emailed, "event": event}


def thresholds() -> dict[str, Any]:
    return {
        "cpu_pct": settings.MONITOR_CPU_ALERT_PCT,
        "memory_pct": settings.MONITOR_MEMORY_ALERT_PCT,
        "disk_pct": settings.MONITOR_DISK_ALERT_PCT,
        "db_latency_ms": settings.MONITOR_DB_LATENCY_ALERT_MS,
        "p95_ms": settings.MONITOR_P95_ALERT_MS,
        "error_rate_pct": settings.MONITOR_ERROR_RATE_ALERT_PCT,
        "backup_max_age_hours": settings.MONITOR_BACKUP_MAX_AGE_HOURS,
        "cert_days": settings.MONITOR_CERT_ALERT_DAYS,
        "cooldown_minutes": settings.MONITOR_ALERT_COOLDOWN_MINUTES,
    }


# --------------------------------------------------------- launch readiness


def _item(key: str, area: str, label: str, ok: bool | None, fix: str, *, warn_only: bool = False) -> dict:
    if ok is None:
        status = "warn"
    elif ok:
        status = "pass"
    else:
        status = "warn" if warn_only else "fail"
    return {"key": key, "area": area, "label": label, "status": status, "fix": "" if ok else fix}



def backups_fix_text(backups: dict) -> str:
    """Why no company backup finished recently, and what to do."""
    age = backups.get("age_hours")
    parts = []
    if age is None:
        parts.append("No company backup has ever finished.")
    else:
        parts.append(f"The last company backup finished {age:g} hours ago.")
    if backups.get("dir_writable") is False:
        parts.append(
            f"The backup folder ({settings.BACKUP_DIR}) cannot be written to by the app. On the server run: "
            "docker run --rm -v <project>_backup_data:/d alpine chown -R 10001:10001 /d (the app runs as user 10001)."
        )
    if backups.get("last_error"):
        parts.append(f"Last error: {backups['last_error']}")
    if int(backups.get("failed_last_24h") or 0):
        parts.append(f"{backups['failed_last_24h']} backup(s) failed in the last day: check the backup folder ({settings.BACKUP_DIR}) is writable and has space.")
    if not int(backups.get("companies_scheduled") or 0):
        parts.append("No company has scheduled backups turned on.")
    parts.append(
        "Daily backups are on by default; check celery_worker and celery_beat are running "
        "(beat runs run_due_backups every hour), or run it now from Jobs > run_due_backups."
    )
    return " ".join(parts)


# --- Launch checks: encryption keys and the metrics token ------------------------------------

_KEY_NAMES = ("BACKUP_ENCRYPTION_KEY", "TOTP_ENCRYPTION_KEY", "SECRETS_ENCRYPTION_KEY")
KEY_COMMAND = 'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'


def _placeholder(value: str) -> bool:
    v = value.strip().upper()
    return not v or v.startswith("REPLACE_ME") or v in {"CHANGEME", "CHANGE_ME", "SECRET", "TEST"}


def key_problems() -> list[str]:
    """What is wrong with the three encryption keys: missing, placeholder, too short, or shared."""
    values = {name: (getattr(settings, name, "") or "").strip() for name in _KEY_NAMES}
    problems = []
    for name, value in values.items():
        if _placeholder(value):
            problems.append(f"{name} is not set")
        elif len(value) < 32:
            problems.append(f"{name} is shorter than 32 characters")
    real = [v for v in values.values() if not _placeholder(v)]
    if len(set(real)) < len(real):
        problems.append("two of the keys are the same value; each needs its own")
    jwt = (settings.JWT_SECRET_KEY or "").strip()
    if jwt and jwt in real:
        problems.append("a key equals JWT_SECRET_KEY; use a different value")
    return problems


def keys_fix_text() -> str:
    problems = key_problems()
    if not problems:
        return "All three keys are set and different. Keep a copy offline: without them backups and saved secrets cannot be opened."
    return (
        "; ".join(problems).capitalize() + ". "
        f"Make each key with: {KEY_COMMAND} and add it in Dokploy > Environment, then redeploy. "
        "Data saved before still opens with the old key. Afterwards run scripts/reencrypt_secrets.py --apply "
        "to move stored secrets onto the new keys. Keep copies offline."
    )


def metrics_problem() -> str | None:
    """None when /metrics is safe: turned off, or behind a real token."""
    if not settings.METRICS_ENABLED:
        return None
    token = (settings.METRICS_TOKEN or "").strip()
    if _placeholder(token):
        closed = settings.APP_ENV.lower() == "production"
        return (
            ("The metrics page is closed (production without a token), so Prometheus cannot read it. " if closed
             else "The metrics page is open to anyone. ")
            + 'Set METRICS_TOKEN to a long random value (python -c "import secrets; print(secrets.token_urlsafe(32))") '
            "and give the same token to Prometheus as a bearer token, or set METRICS_ENABLED=false."
        )
    if len(token) < 24:
        return "METRICS_TOKEN is shorter than 24 characters. Use a long random value (secrets.token_urlsafe(32))."
    return None

async def launch_checks(db: AsyncSession, snap: dict[str, Any] | None = None) -> dict[str, Any]:
    """Commercial launch checklist for the software owner (no secrets returned)."""
    from app import platform_settings as platform_settings_svc

    if snap is None:
        snap = await collect_snapshot(db, source="api")
    prod = settings.APP_ENV.lower() == "production"
    try:
        ps = await platform_settings_svc.build_platform_settings(db)
        billing = ps.get("billing") or {}
    except Exception:
        billing = {}
    checks = {c["key"]: c for c in snap.get("checks") or []}
    url = _public_url()
    workers = snap.get("workers") or {}
    backups = snap.get("backups") or {}
    tls = snap.get("tls") or {}
    redis = snap.get("redis") or {}
    disk = checks.get("disk", {}).get("status")
    items = [
        _item("env", "Server", "Running in production mode", prod, "Set APP_ENV=production on the server."),
        _item("channel", "Server", "Production release channel",
              (settings.RIBDIGI_RELEASE_CHANNEL or "").lower() == "production",
              "Deploy from the production branch (RIBDIGI_RELEASE_CHANNEL=production)."),
        _item("debug", "Server", "Debug and API explorer switched off", not settings.DEBUG and prod,
              "Set DEBUG=false; /docs is hidden automatically in production."),
        _item("https", "Server", "Public address uses https", url.startswith("https://"),
              "Set FRONTEND_URL (or MONITOR_PUBLIC_URL) to the https address customers use."),
        _item("tls", "Server", "Security certificate valid for 14+ days",
              tls.get("status") == "ok" and tls.get("days_left", 0) > settings.MONITOR_CERT_ALERT_DAYS
              if tls.get("status") != "skipped" else None,
              "Renew the TLS certificate (Dokploy / Traefik renews Let's Encrypt automatically)."),
        _item("disk", "Server", "Enough free disk space", disk in ("ok", None),
              "Free space on the VPS: clear old backups, Docker images (docker system prune) or grow the disk."),
        _item("redis", "Server", "Redis running (shared rate limits, monitor history)",
              redis.get("status") == "ok", "Start Redis and set REDIS_URL.", warn_only=True),
        _item("workers", "Server", "Background workers answering",
              workers.get("status") in ("ok",) if settings.CELERY_ENABLED else False,
              "Start celery_worker and celery_beat (emails, backups, renewals and alerts run there)."),
        _item("2fa", "Security", "Two-step sign-in enforced", bool(settings.LOGIN_2FA_ENABLED),
              "Set LOGIN_2FA_ENABLED=true."),
        _item("keys", "Security", "Separate encryption keys set", not key_problems(), keys_fix_text(), warn_only=False),
        _item("metrics", "Security", "Metrics page protected by a token", not metrics_problem(),
              metrics_problem() or "Metrics are protected.", warn_only=True),
        _item("email", "Customers", "Platform email can send",
              bool(settings.EMAIL_ENABLED and (settings.SMTP_HOST or "").strip()),
              "Set SMTP_HOST, SMTP_FROM_EMAIL and credentials so sign-up, reset and invoice mail is delivered."),
        _item("billing", "Customers", "Live payment gateway taking real charges", bool(billing.get("live_charges")),
              "Platform > Billing > Gateway: add live keys, test, then enable."),
        _item("backups", "Data", "A backup finished in the last day and a half",
              backups.get("age_hours") is not None and backups["age_hours"] <= settings.MONITOR_BACKUP_MAX_AGE_HOURS,
              backups_fix_text(backups)),
        _item("offsite", "Data", "Files and backups stored off the server",
              (settings.STORAGE_BACKEND or "local").lower() == "s3",
              "Set STORAGE_BACKEND=s3 (any S3/MinIO bucket) so a lost VPS does not lose uploads.", warn_only=True),
        _item("alerts", "Monitoring", "Monitor history running (scheduled every minute)",
              not workers.get("scheduled_jobs_stale"),
              "Start celery_beat; the monitor job records a reading every minute.", warn_only=True),
    ]
    counts = {s: sum(1 for i in items if i["status"] == s) for s in ("pass", "warn", "fail")}
    return {"items": items, "counts": counts, "ready": counts["fail"] == 0}
