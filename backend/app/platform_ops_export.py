"""Platform house ops CSV export helpers (Stage 151).

Honesty: health/evidence CSVs surface operator posture and packaging honesty —
not fabricated billing Completes or live payment rails (ADR-002). At-risk
tenant rows reuse the same risk signals as GET /platform/tenants/at-risk.
"""

from __future__ import annotations

import csv
import io
from typing import Any


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _check_detail(check: dict[str, Any]) -> str:
    parts: list[str] = []
    if check.get("required") is True:
        parts.append("required")
    elif check.get("required") is False:
        parts.append("optional")
    if check.get("latency_ms") is not None:
        parts.append(f"{check.get('latency_ms')}ms")
    if check.get("mode"):
        parts.append(str(check.get("mode")))
    if check.get("reason"):
        parts.append(str(check.get("reason")))
    if check.get("error"):
        parts.append(str(check.get("error")))
    return " · ".join(parts)


def _iter_checks(checks: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(checks, dict):
        out: list[tuple[str, dict[str, Any]]] = []
        for name, check in checks.items():
            if isinstance(check, dict):
                out.append((str(name), check))
        return out
    if isinstance(checks, list):
        out = []
        for check in checks:
            if isinstance(check, dict):
                out.append((_cell(check.get("name") or "check"), check))
        return out
    return []


def _write_kv_rows(
    writer: Any,
    *,
    row_type: str,
    section: str,
    mapping: dict[str, Any] | None,
    generated_at: object,
) -> None:
    if not mapping:
        return
    for key, value in mapping.items():
        if isinstance(value, (dict, list)):
            value = str(value)
        writer.writerow(
            [
                row_type,
                section,
                _cell(key),
                _cell(value),
                "",
                "",
                _cell(generated_at),
            ]
        )


def export_platform_health_csv(
    *,
    health_payload: dict[str, Any],
    operator_contacts: dict[str, Any] | None = None,
    security: dict[str, Any] | None = None,
    house_runtime: dict[str, Any] | None = None,
    runtime_identity: dict[str, Any] | None = None,
) -> bytes:
    """Flatten GET /platform/health JSON into multi-row_type CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_type",
            "section",
            "key",
            "value",
            "status",
            "detail",
            "generated_at",
        ]
    )
    generated = health_payload.get("generated_at") or health_payload.get("timestamp")
    writer.writerow(
        [
            "summary",
            "health",
            "status",
            _cell(health_payload.get("status")),
            _cell(health_payload.get("status")),
            "",
            _cell(generated),
        ]
    )
    for key in ("service", "deep", "env", "environment"):
        if key in health_payload:
            writer.writerow(
                [
                    "summary",
                    "health",
                    key,
                    _cell(health_payload.get(key)),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    for name, check in _iter_checks(health_payload.get("checks")):
        writer.writerow(
            [
                "check",
                "health",
                name,
                "",
                _cell(check.get("status")),
                _check_detail(check),
                _cell(generated),
            ]
        )
    contacts = operator_contacts if operator_contacts is not None else health_payload.get("operator_contacts")
    sec = security if security is not None else health_payload.get("security")
    runtime = house_runtime if house_runtime is not None else health_payload.get("house_runtime")
    identity = (
        runtime_identity
        if runtime_identity is not None
        else health_payload.get("runtime_identity")
    )
    _write_kv_rows(
        writer,
        row_type="operator_contact",
        section="contacts",
        mapping=contacts if isinstance(contacts, dict) else None,
        generated_at=generated,
    )
    _write_kv_rows(
        writer,
        row_type="security",
        section="security",
        mapping=sec if isinstance(sec, dict) else None,
        generated_at=generated,
    )
    _write_kv_rows(
        writer,
        row_type="house_runtime",
        section="runtime",
        mapping=runtime if isinstance(runtime, dict) else None,
        generated_at=generated,
    )
    _write_kv_rows(
        writer,
        row_type="runtime_identity",
        section="identity",
        mapping=identity if isinstance(identity, dict) else None,
        generated_at=generated,
    )
    return buf.getvalue().encode("utf-8")


def export_platform_evidence_csv(*, evidence: dict[str, Any]) -> bytes:
    """Flatten GET /platform/evidence packaging honesty into multi-row_type CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_type",
            "section",
            "key",
            "value",
            "status",
            "detail",
            "generated_at",
        ]
    )
    generated = evidence.get("generated_at")
    for key in ("packaging_only", "note", "schema_version"):
        if key in evidence:
            writer.writerow(
                [
                    "meta",
                    "evidence",
                    key,
                    _cell(evidence.get(key)),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    honesty = evidence.get("honesty_flags")
    if isinstance(honesty, dict):
        for key, value in honesty.items():
            writer.writerow(
                [
                    "honesty_flag",
                    "honesty_flags",
                    _cell(key),
                    _cell(value),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    health = evidence.get("health") if isinstance(evidence.get("health"), dict) else {}
    writer.writerow(
        [
            "health_summary",
            "health",
            "status",
            _cell(health.get("status")),
            _cell(health.get("status")),
            "",
            _cell(generated),
        ]
    )
    for name, check in _iter_checks(health.get("checks")):
        writer.writerow(
            [
                "health_check",
                "health",
                name,
                "",
                _cell(check.get("status")),
                _check_detail(check),
                _cell(generated),
            ]
        )
    for section_key, row_type in (
        ("security", "security"),
        ("operator_contacts", "operator_contact"),
        ("house_runtime", "house_runtime"),
        ("runtime_identity", "runtime_identity"),
        ("house", "house"),
    ):
        section = evidence.get(section_key)
        if isinstance(section, dict):
            flat: dict[str, Any] = {}
            for key, value in section.items():
                if isinstance(value, (dict, list)) and key == "checks":
                    continue
                if isinstance(value, (dict, list)):
                    flat[key] = str(value)
                else:
                    flat[key] = value
            _write_kv_rows(
                writer,
                row_type=row_type,
                section=section_key,
                mapping=flat,
                generated_at=generated,
            )
    return buf.getvalue().encode("utf-8")


def export_platform_at_risk_tenants_csv(*, items: list[Any], within_days: int | None = None) -> bytes:
    """Flatten GET /platform/tenants/at-risk JSON into CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "tenant_id",
            "slug",
            "company_name",
            "status",
            "plan_code",
            "trial_ends_at",
            "grace_ends_at",
            "risk_ends_at",
            "days_remaining",
            "within_days",
            "platform_notes",
        ]
    )
    for item in items:
        if isinstance(item, dict):
            get = item.get
        else:
            get = lambda k, default=None, _item=item: getattr(_item, k, default)
        writer.writerow(
            [
                _cell(get("id") or get("tenant_id")),
                _cell(get("slug")),
                _cell(get("company_name") or get("name")),
                _cell(get("status")),
                _cell(get("plan_code")),
                _cell(get("trial_ends_at")),
                _cell(get("grace_ends_at")),
                _cell(get("risk_ends_at")),
                _cell(get("days_remaining")),
                _cell(get("within_days") if get("within_days") is not None else within_days),
                _cell(get("platform_notes")),
            ]
        )
    return buf.getvalue().encode("utf-8")


def export_platform_dashboard_csv(*, dashboard: dict[str, Any]) -> bytes:
    """Flatten GET /platform/dashboard JSON into multi-row_type CSV (Stage 152 G1).

    Honesty: KPI aggregates only — billing/MRR stay deferred (ADR-002); no fabricated revenue.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_type",
            "section",
            "key",
            "value",
            "label",
            "count",
            "generated_at",
        ]
    )
    generated = dashboard.get("generated_at")
    kpi_keys = (
        "total_tenants",
        "active_tenants",
        "trial_tenants",
        "grace_tenants",
        "suspended_tenants",
        "at_risk_count",
        "at_risk_within_days",
        "new_tenants_this_month",
        "platform_users",
        "customer_users",
    )
    for key in kpi_keys:
        if key in dashboard:
            writer.writerow(
                [
                    "kpi",
                    "summary",
                    key,
                    _cell(dashboard.get(key)),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    billing = dashboard.get("billing") if isinstance(dashboard.get("billing"), dict) else {}
    for key, value in billing.items():
        writer.writerow(
            [
                "billing",
                "billing",
                _cell(key),
                _cell(value),
                "",
                "",
                _cell(generated),
            ]
        )
    status_breakdown = dashboard.get("status_breakdown")
    if isinstance(status_breakdown, dict):
        for status, count in status_breakdown.items():
            writer.writerow(
                [
                    "status_breakdown",
                    "status",
                    _cell(status),
                    _cell(count),
                    _cell(status),
                    _cell(count),
                    _cell(generated),
                ]
            )

    def _series(section: str, payload: Any, label_key: str, value_key: str) -> None:
        if not isinstance(payload, dict):
            return
        series = payload.get("series") or payload.get("slices") or []
        if not isinstance(series, list):
            return
        for point in series:
            if not isinstance(point, dict):
                continue
            label = point.get(label_key) or point.get("label") or point.get("month")
            count = point.get(value_key) or point.get("count") or point.get("value")
            writer.writerow(
                [
                    "series" if payload.get("series") is not None else "slice",
                    section,
                    _cell(label),
                    _cell(count),
                    _cell(label),
                    _cell(count),
                    _cell(generated),
                ]
            )

    _series("tenant_growth", dashboard.get("tenant_growth"), "month", "tenants")
    _series("tenant_status", dashboard.get("tenant_status"), "status", "count")
    _series("plan_distribution", dashboard.get("plan_distribution"), "plan_code", "count")
    _series("industry_distribution", dashboard.get("industry_distribution"), "industry", "count")
    _series("user_growth", dashboard.get("user_growth"), "month", "users")
    return buf.getvalue().encode("utf-8")
