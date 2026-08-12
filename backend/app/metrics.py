"""Lightweight Prometheus-text metrics (Stage 5 H5; no full Grafana stack)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import DefaultDict

from app.config import settings

_STARTED_AT = time.time()
_lock = threading.Lock()
_request_total: DefaultDict[tuple[str, str], int] = defaultdict(int)
_request_duration_sum: DefaultDict[str, float] = defaultdict(float)
_request_duration_count: DefaultDict[str, int] = defaultdict(int)


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


def reset_for_tests() -> None:
    with _lock:
        _request_total.clear()
        _request_duration_sum.clear()
        _request_duration_count.clear()


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
