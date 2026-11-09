"""Small shared pieces for the desk dashboards: a daily series, a monthly series, and a
"needs you now" item. Each desk still reads only its own tables; this file holds no queries.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.honesty import money_json

TREND_DAYS = 14


def window(days: int = TREND_DAYS, *, end: date | None = None) -> tuple[date, datetime, datetime]:
    """First day, and the datetime bounds, of the last ``days`` days ending today."""
    last = end or date.today()
    first = last - timedelta(days=days - 1)
    return first, datetime.combine(first, time.min), datetime.combine(last, time.max)


def daily(points: dict[date, float], *, first: date, days: int = TREND_DAYS) -> list[dict]:
    """One row a day, oldest first, with zero for days that had nothing."""
    return [
        {"date": (first + timedelta(days=i)).isoformat(), "value": money_json(round(points.get(first + timedelta(days=i), 0.0), 2))}
        for i in range(days)
    ]


def months_back(count: int, *, today: date | None = None) -> list[str]:
    """``YYYY-MM`` keys for the last ``count`` months, oldest first, this month last."""
    day = (today or date.today()).replace(day=1)
    keys = []
    for _ in range(count):
        keys.append(day.strftime("%Y-%m"))
        day = (day - timedelta(days=1)).replace(day=1)
    return list(reversed(keys))


def trend(label: str, unit: str, rows: list[dict], *, step: str = "day") -> dict:
    return {"label": label, "unit": unit, "step": step, "points": rows}


def item(level: str, text: str, href: str) -> dict:
    """A line under "Needs you now". ``level`` is ``warning`` or ``info``."""
    return {"level": level, "text": text, "href": href}


def plural(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"
