"""Lightweight Prometheus-text metrics (Stage 5 H5; no full Grafana stack)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import DefaultDict

from app.config import settings

_STARTED_AT = time.time()
_lock = threading.Lock()
_request_total: DefaultDict[tuple[str, str], int] = defaultdict(int)
_request_duration_sum: DefaultDict[str, float] = defaultdict(float)
_request_duration_count: DefaultDict[str, int] = defaultdict(int)
# Rolling window of recent requests for the owner's server monitor:
# (unix time, seconds, status code, path group). Health/metrics probes are left out.
_RECENT_MAX = 20_000
_recent: deque[tuple[float, float, int, str]] = deque(maxlen=_RECENT_MAX)
_PROBE_GROUPS = frozenset({"/api/v1/health", "/api/v1/metrics"})


def metrics_enabled() -> bool:
    return bool(getattr(settings, "METRICS_ENABLED", True))


def observe_request(*, method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record one HTTP request. Paths are grouped to avoid high cardinality."""
    if not metrics_enabled():
        return
    group = _path_group(path)
    method_u = (method or "GET").upper()
    code = str(int(status_code))
    with _lock:
        _request_total[(method_u, code)] += 1
        _request_duration_sum[group] += float(duration_seconds)
        _request_duration_count[group] += 1
        if group not in _PROBE_GROUPS and not (path or "").startswith("/api/v1/platform/monitor"):
            _recent.append((time.time(), float(duration_seconds), int(status_code), group))


def reset_for_tests() -> None:
    with _lock:
        _request_total.clear()
        _request_duration_sum.clear()
        _request_duration_count.clear()
        _recent.clear()


def process_started_at() -> float:
    return _STARTED_AT


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def recent_performance(window_seconds: int = 900) -> dict:
    """Request speed and errors for this API worker over the last ``window_seconds``."""
    cutoff = time.time() - max(1, int(window_seconds))
    with _lock:
        rows = [r for r in _recent if r[0] >= cutoff]
    total = len(rows)
    durations = sorted(r[1] for r in rows)
    errors = sum(1 for r in rows if r[2] >= 500)
    client_errors = sum(1 for r in rows if 400 <= r[2] < 500)
    by_group: dict[str, list[float]] = defaultdict(list)
    group_errors: DefaultDict[str, int] = defaultdict(int)
    for _, dur, code, group in rows:
        by_group[group].append(dur)
        if code >= 500:
            group_errors[group] += 1
    slowest = sorted(
        (
            {
                "path_group": g,
                "requests": len(v),
                "avg_ms": round(sum(v) / len(v) * 1000.0, 1),
                "p95_ms": round(_percentile(sorted(v), 0.95) * 1000.0, 1),
                "errors": group_errors.get(g, 0),
            }
            for g, v in by_group.items()
        ),
        key=lambda x: x["p95_ms"],
        reverse=True,
    )[:8]
    minutes = max(1.0, window_seconds / 60.0)
    return {
        "window_seconds": int(window_seconds),
        "requests": total,
        "requests_per_minute": round(total / minutes, 2),
        "server_errors": errors,
        "client_errors": client_errors,
        "error_rate_pct": round(errors / total * 100.0, 2) if total else 0.0,
        "avg_ms": round(sum(durations) / total * 1000.0, 1) if total else 0.0,
        "p50_ms": round(_percentile(durations, 0.50) * 1000.0, 1),
        "p95_ms": round(_percentile(durations, 0.95) * 1000.0, 1),
        "p99_ms": round(_percentile(durations, 0.99) * 1000.0, 1),
        "slowest": slowest,
    }


def _path_group(path: str) -> str:
    p = path or "/"
    if p.startswith("/api/v1/health"):
        return "/api/v1/health"
    if p.startswith("/api/v1/metrics"):
        return "/api/v1/metrics"
    if p.startswith("/api/v1/auth"):
        return "/api/v1/auth"
    if p.startswith("/api/v1/"):
        # Collapse /api/v1/<segment>/...
        parts = p.strip("/").split("/")
        if len(parts) >= 3:
            return f"/api/v1/{parts[2]}"
        return "/api/v1"
    if p == "/":
        return "/"
    return "other"


def render_prometheus() -> str:
    """Return Prometheus exposition format (text/plain; version 0.0.4)."""
    lines: list[str] = [
        "# HELP ribdigi_up API process up flag.",
        "# TYPE ribdigi_up gauge",
        "ribdigi_up 1",
        "# HELP ribdigi_process_start_time_seconds Process start time as Unix timestamp.",
        "# TYPE ribdigi_process_start_time_seconds gauge",
        f"ribdigi_process_start_time_seconds {_STARTED_AT:.3f}",
        "# HELP ribdigi_app_info Build/app labels.",
        "# TYPE ribdigi_app_info gauge",
        f'ribdigi_app_info{{service="ribdigi-erp",env="{_escape(settings.APP_ENV)}"}} 1',
        "# HELP ribdigi_http_requests_total Total HTTP requests by method and status.",
        "# TYPE ribdigi_http_requests_total counter",
    ]
    with _lock:
        totals = list(_request_total.items())
        dur_sum = dict(_request_duration_sum)
        dur_count = dict(_request_duration_count)

    for (method, code), count in sorted(totals):
        lines.append(
            f'ribdigi_http_requests_total{{method="{_escape(method)}",status="{_escape(code)}"}} {count}'
        )

    lines.append("# HELP ribdigi_http_request_duration_seconds_sum Request duration sum by path group.")
    lines.append("# TYPE ribdigi_http_request_duration_seconds_sum counter")
    for group, total in sorted(dur_sum.items()):
        lines.append(
            f'ribdigi_http_request_duration_seconds_sum{{path_group="{_escape(group)}"}} {total:.6f}'
        )
    lines.append("# HELP ribdigi_http_request_duration_seconds_count Request duration count by path group.")
    lines.append("# TYPE ribdigi_http_request_duration_seconds_count counter")
    for group, count in sorted(dur_count.items()):
        lines.append(
            f'ribdigi_http_request_duration_seconds_count{{path_group="{_escape(group)}"}} {count}'
        )

    lines.append("")
    return "\n".join(lines)


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )
