"""Plain-language server alert emails for platform staff.

One email per check-up, however many checks changed: it says what is wrong in
one sentence, shows the reading against its limit, explains what that means for
customers, and lists what to do, with a button to Server health.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from app.config import settings

# What each check means for customers, and what to do about it.
HELP: dict[str, dict[str, Any]] = {
    "cpu": {
        "means": "The server's processor is nearly fully busy. Pages, saves and reports get slow for every company.",
        "do": [
            "Open Server health and look at Slowest areas to see what is busy.",
            "If it stays high for more than 15 minutes, restart the backend in Dokploy.",
            "If this happens often, move to a VPS with more processor cores.",
        ],
    },
    "memory": {
        "means": "The server is running out of memory. When it runs out, the system can stop the app without warning.",
        "do": [
            "Restart the backend and the celery worker in Dokploy to free memory.",
            "Check Server health → Services for anything using unusual memory.",
            "If this happens often, add memory (RAM) to the VPS.",
        ],
    },
    "disk": {
        "means": "The server's disk is filling up. When it is full, saving records, uploads and backups all fail.",
        "do": [
            "Remove unused Docker images: on the server run  docker image prune -a  (it only removes images no running app uses).",
            "Delete old backup files beyond your retention, or move them off the server.",
            "If the disk is genuinely full of data, grow the disk with your VPS provider.",
        ],
    },
    "database": {
        "means": "The main database is slow or not answering. Companies cannot load or save records.",
        "do": [
            "In Dokploy, check the postgres service is running; restart it if it is not.",
            "Check disk space on Server health; a full disk stops the database.",
            "If it is only slow, look for long-running reports in Server health → Services.",
        ],
    },
    "desk_db": {
        "means": "One industry desk's database is not answering. Companies on that desk cannot work.",
        "do": [
            "In Dokploy, check that desk's database service is running and restart it if needed.",
            "Check the DESK_DATABASE_URLS setting still points at the right server.",
        ],
    },
    "redis": {
        "means": "Redis is down. Sign-in limits and the monitor's history stop being shared, and some screens slow down.",
        "do": [
            "In Dokploy, restart the redis service.",
            "Check REDIS_URL is set on the backend and the workers.",
        ],
    },
    "workers": {
        "means": "Background workers are not answering. Emails, backups, subscription renewals and these alerts wait until they are back.",
        "do": [
            "In Dokploy, restart celery_worker.",
            "Check the rabbitmq service is running (the workers need it).",
        ],
    },
    "scheduler": {
        "means": "Scheduled jobs have stopped. Backups, renewals and reminder emails are not running on time.",
        "do": [
            "In Dokploy, restart celery_beat (and celery_worker if it is also down).",
        ],
    },
    "latency": {
        "means": "Pages are answering slowly. Customers will notice delays when they open screens or save.",
        "do": [
            "Open Server health → Slowest areas to see which part is slow.",
            "Check the processor and database readings on the same page.",
            "If it started after a deploy, consider rolling back that deploy in Dokploy.",
        ],
    },
    "errors": {
        "means": "Many requests are failing with server errors. Customers see 'something went wrong' messages.",
        "do": [
            "Open the backend logs in Dokploy and look for the newest errors.",
            "If it started right after a deploy, roll back to the previous deploy.",
        ],
    },
    "backups": {
        "means": "No backup has finished recently. If something breaks, recent company data could be lost.",
        "do": [
            "Open the Backup page and check the latest backup and any error.",
            "Make sure celery_worker and celery_beat are running; scheduled backups need them.",
            "Check there is free disk space for the backup files.",
        ],
    },
    "web": {
        "means": "The public website is not reachable. Customers cannot open Ribdigi or sign in.",
        "do": [
            "In Dokploy, check the frontend and backend services are running.",
            "Check the domain and its DNS still point at this server.",
        ],
    },
    "tls": {
        "means": "The security certificate is close to expiring or cannot be read. When it expires, browsers block the site with a warning.",
        "do": [
            "In Dokploy, open the domain settings and renew or re-issue the certificate.",
            "Make sure port 80 is open so Let's Encrypt can renew automatically.",
        ],
    },
}

LIMITS = {
    "cpu": lambda: f"{settings.MONITOR_CPU_ALERT_PCT:.0f}%",
    "memory": lambda: f"{settings.MONITOR_MEMORY_ALERT_PCT:.0f}%",
    "disk": lambda: f"{settings.MONITOR_DISK_ALERT_PCT:.0f}% used",
    "database": lambda: f"{settings.MONITOR_DB_LATENCY_ALERT_MS:.0f} ms",
    "latency": lambda: f"{settings.MONITOR_P95_ALERT_MS:.0f} ms",
    "errors": lambda: f"{settings.MONITOR_ERROR_RATE_ALERT_PCT:g}% of requests",
    "backups": lambda: f"older than {settings.MONITOR_BACKUP_MAX_AGE_HOURS:g} hours",
    "tls": lambda: f"under {settings.MONITOR_CERT_ALERT_DAYS} days",
}

RED = "#C2362F"
GREEN = "#2E8B37"
BLUE = "#3B82D6"
INK = "#10211B"
MUTED = "#55695E"
LINE = "#E3EBDA"


def _base(key: str) -> str:
    return key.split(":", 1)[0]


def help_for(key: str) -> dict[str, Any]:
    return HELP.get(_base(key)) or {
        "means": "A server check is failing.",
        "do": ["Open Server health for the full picture."],
    }


def limit_for(key: str) -> str:
    fn = LIMITS.get(_base(key))
    return fn() if fn else "must be up"


def _when(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return value


def _lasted(since: str | None, until: str | None) -> str | None:
    try:
        a = datetime.fromisoformat(str(since))
        b = datetime.fromisoformat(str(until))
    except Exception:
        return None
    minutes = max(1, int((b - a).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins} min" if mins else f"{hours} hour{'s' if hours != 1 else ''}"


def monitor_url() -> str:
    base = (settings.FRONTEND_URL or "").strip().rstrip("/")
    return f"{base}/platform/monitor" if base else "/platform/monitor"


def _row(label: str, value: str, *, strong: bool = False) -> str:
    weight = "700" if strong else "400"
    return (
        f'<tr><td style="padding:8px 12px 8px 0;color:{MUTED};font-size:14px;width:130px;vertical-align:top;">'
        f"{html.escape(label)}</td>"
        f'<td style="padding:8px 0;color:{INK};font-size:14px;font-weight:{weight};">{html.escape(value)}</td></tr>'
    )


def _banner(colour: str, word: str, headline: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin:0 0 18px;">'
        f'<tr><td style="border-left:5px solid {colour};background:#F6F9F2;padding:14px 16px;border-radius:8px;">'
        f'<div style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{colour};">'
        f"{html.escape(word)}</div>"
        f'<div style="margin-top:4px;font-size:19px;line-height:1.35;font-weight:700;color:{INK};">'
        f"{html.escape(headline)}</div></td></tr></table>"
    )


def _problem_block(item: dict[str, Any], host: str, *, numbered: int | None) -> str:
    key = item["key"]
    info = help_for(key)
    title = item["label"] if numbered is None else f"{numbered}. {item['label']}"
    rows = "".join(
        [
            _row("Reading now", item.get("value") or "—", strong=True),
            _row("Alert limit", limit_for(key)),
            _row("Server", host),
            _row("Started", _when(item.get("since") or item.get("at"))),
        ]
    )
    steps = "".join(
        f'<li style="margin:0 0 6px;color:{INK};font-size:14px;line-height:1.5;">{html.escape(s)}</li>'
        for s in info["do"]
    )
    detail = item.get("detail") or ""
    return (
        f'<h2 style="margin:22px 0 6px;font-size:17px;color:{INK};">{html.escape(title)}</h2>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
        f'border-top:1px solid {LINE};border-bottom:1px solid {LINE};width:100%;margin:0 0 12px;">{rows}</table>'
        + (f'<p style="margin:0 0 10px;color:{MUTED};font-size:13px;">{html.escape(detail)}</p>' if detail else "")
        + f'<p style="margin:0 0 4px;font-size:13px;font-weight:700;color:{INK};">What this means</p>'
        f'<p style="margin:0 0 12px;color:{INK};font-size:14px;line-height:1.55;">{html.escape(info["means"])}</p>'
        f'<p style="margin:0 0 4px;font-size:13px;font-weight:700;color:{INK};">What to do</p>'
        f'<ol style="margin:0 0 4px;padding-left:20px;">{steps}</ol>'
    )


def _footer() -> str:
    return (
        f'<p style="margin:22px 0 0;color:{MUTED};font-size:12.5px;line-height:1.5;">'
        "You get this because you are Ribdigi platform staff. Each alert repeats at most every "
        f"{settings.MONITOR_ALERT_COOLDOWN_MINUTES} minutes while the problem lasts, and you will get a "
        "“resolved” email when it is fixed. To stop these emails, open Notifications → Server health "
        "and turn off email.</p>"
    )


def build_alert_email(items: list[dict[str, Any]], host: str) -> tuple[str, str, str]:
    """(subject, plain text, inner HTML) for one or more new problems."""
    from app import emailer

    n = len(items)
    first = items[0]
    if n == 1:
        subject = f"Action needed: {first['label']} on {host} is {first['value']}"
        headline = f"{first['label']} is {first['value']} on {host}."
    else:
        names = ", ".join(i["label"] for i in items[:3]) + (" and more" if n > 3 else "")
        subject = f"Action needed: {n} server problems on {host} ({names})"
        headline = f"{n} things need attention on {host}: {names}."
    url = monitor_url()
    inner = (
        _banner(RED, "Action needed", headline)
        + f'<p style="margin:0;color:{INK};font-size:14px;line-height:1.55;">'
        "The Ribdigi server monitor found a problem. Here is what it is and how to fix it.</p>"
        + "".join(_problem_block(item, host, numbered=(i + 1) if n > 1 else None) for i, item in enumerate(items))
        + '<div style="margin:22px 0 10px;">'
        + emailer.email_button(url, "Open Server health")
        + "</div>"
        + emailer._link_fallback(url)
        + _footer()
    )
    lines = [headline, "", "The Ribdigi server monitor found a problem.", ""]
    for i, item in enumerate(items):
        info = help_for(item["key"])
        lines += [
            f"{(str(i + 1) + '. ') if n > 1 else ''}{item['label']}",
            f"  Reading now: {item.get('value')}",
            f"  Alert limit: {limit_for(item['key'])}",
            f"  Server: {host}",
            f"  Started: {_when(item.get('since') or item.get('at'))}",
            f"  What this means: {info['means']}",
            "  What to do:",
            *[f"   - {s}" for s in info["do"]],
            "",
        ]
    lines += [f"Open Server health: {url}", "", "To stop these emails: Notifications → Server health → turn off email."]
    return subject, "\n".join(lines), inner


def build_recovered_email(items: list[dict[str, Any]], host: str) -> tuple[str, str, str]:
    """(subject, plain text, inner HTML) for problems that are fixed."""
    from app import emailer

    n = len(items)
    if n == 1:
        subject = f"Resolved: {items[0]['label']} on {host} is back to normal"
        headline = f"{items[0]['label']} is back to normal on {host}."
    else:
        subject = f"Resolved: {n} server problems on {host} are back to normal"
        headline = f"{n} problems are back to normal on {host}."
    rows = ""
    text_rows: list[str] = []
    for item in items:
        lasted = _lasted(item.get("since"), item.get("at"))
        value = f"Back to normal{f' after {lasted}' if lasted else ''} (now {item.get('value') or 'ok'})"
        rows += _row(item["label"], value)
        text_rows.append(f"- {item['label']}: {value}")
    url = monitor_url()
    inner = (
        _banner(GREEN, "Resolved", headline)
        + f'<p style="margin:0 0 12px;color:{INK};font-size:14px;line-height:1.55;">'
        "Nothing more to do for these. If customers reported issues while it was happening, you can let them know it is fixed.</p>"
        + f'<table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
        f'border-top:1px solid {LINE};border-bottom:1px solid {LINE};width:100%;">{rows}</table>'
        + '<div style="margin:22px 0 10px;">'
        + emailer.email_button(url, "Open Server health")
        + "</div>"
        + _footer()
    )
    text = "\n".join([headline, "", *text_rows, "", f"Open Server health: {url}"])
    return subject, text, inner


def build_test_email(by: str, host: str) -> tuple[str, str, str]:
    from app import emailer

    url = monitor_url()
    subject = f"Test: Ribdigi server alerts reach you ({host})"
    headline = "Server alerts are working."
    inner = (
        _banner(BLUE, "Test", headline)
        + f'<p style="margin:0 0 12px;color:{INK};font-size:14px;line-height:1.55;">'
        f"{html.escape(by)} sent this test from Server health. Real alerts look like this: a one-line summary, "
        "the reading against its limit, what it means for customers, and the steps to fix it. "
        "Nothing is wrong right now.</p>"
        + '<div style="margin:18px 0 10px;">'
        + emailer.email_button(url, "Open Server health")
        + "</div>"
        + _footer()
    )
    text = f"{headline}\n\n{by} sent this test from Server health. Nothing is wrong right now.\n\n{url}"
    return subject, text, inner
