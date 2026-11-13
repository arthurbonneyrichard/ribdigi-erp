"""Email design: how a company's emails look, and how Ribdigi House's own emails look.

A company keeps its choices in ``tenants.print_branding["email_style"]`` next to the print
header and footer. The software owner's choices live in ``print_branding["platform_email_style"]``
on the platform company. The two use different layouts: company mail has a coloured
letterhead with the company's details, Ribdigi House mail has a white masthead and a dark
footer band, so a customer can always tell which one wrote to them.

Colours come only from the presets below. Each was picked so white text on the header and
button, and the link colour on white, stay readable.
"""

from __future__ import annotations

import time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

ThemeKey = Literal["forest", "emerald", "ocean", "royal", "plum", "terracotta", "charcoal"]
HeaderStyle = Literal["solid", "light", "minimal"]
LogoAlign = Literal["left", "center"]
ButtonShape = Literal["rounded", "pill", "square"]
FontKey = Literal["modern", "classic", "system"]

THEMES: dict[str, dict[str, str]] = {
    # header: band colour; line: accent strip; button: CTA fill; link: link/heading accent;
    # tint: soft panel background; page: outer background.
    "forest": {"label": "Forest", "header": "#003d1f", "line": "#4ab012", "button": "#2f7a0c",
               "link": "#006b2e", "tint": "#f2f7ec", "page": "#eef3e9", "badge": "#c8e86a"},
    "emerald": {"label": "Emerald", "header": "#064e3b", "line": "#34d399", "button": "#047857",
                "link": "#047857", "tint": "#ecfdf5", "page": "#e8f5ef", "badge": "#a7f3d0"},
    "ocean": {"label": "Ocean", "header": "#0b3b66", "line": "#38bdf8", "button": "#0b5cad",
              "link": "#0b5cad", "tint": "#eef4fb", "page": "#e9f0f8", "badge": "#bae6fd"},
    "royal": {"label": "Royal", "header": "#2e1f6b", "line": "#a78bfa", "button": "#5b3fd1",
              "link": "#5b3fd1", "tint": "#f3f0fd", "page": "#eeeaf9", "badge": "#ddd6fe"},
    "plum": {"label": "Plum", "header": "#5b1f4a", "line": "#f472b6", "button": "#9d2a73",
             "link": "#9d2a73", "tint": "#fbf0f6", "page": "#f6ebf1", "badge": "#fbcfe8"},
    "terracotta": {"label": "Terracotta", "header": "#7a2e14", "line": "#fb923c", "button": "#b4471c",
                   "link": "#b4471c", "tint": "#fdf3ec", "page": "#f8ede5", "badge": "#fed7aa"},
    "charcoal": {"label": "Charcoal", "header": "#1f2933", "line": "#f5b301", "button": "#1f2933",
                 "link": "#1f4f8a", "tint": "#f2f4f6", "page": "#eceff2", "badge": "#fde68a"},
}

FONTS: dict[str, str] = {
    "modern": "'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,Helvetica,Arial,sans-serif",
    "classic": "Georgia,'Times New Roman',Times,serif",
    "system": "Arial,Helvetica,sans-serif",
}

BUTTON_RADIUS = {"rounded": "12px", "pill": "999px", "square": "4px"}

TENANT_DEFAULT: dict[str, Any] = {
    "theme": "forest",
    "header_style": "solid",
    "logo_align": "left",
    "button_shape": "rounded",
    "font": "modern",
    "show_details": True,
    "signature": "",
    "footer_text": "",
}

PLATFORM_DEFAULT: dict[str, Any] = {
    "theme": "forest",
    "logo_align": "left",
    "button_shape": "pill",
    "font": "modern",
    "tagline": "Empowering your digital growth",
    "signature": "",
    "footer_text": "",
}

TENANT_KEY = "email_style"
PLATFORM_KEY = "platform_email_style"

_Narrow = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_Footer = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
_Tagline = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class EmailDesignUpdate(BaseModel):
    """Every field optional; ``null`` or blank text clears a text field back to the default."""

    model_config = ConfigDict(extra="forbid")

    theme: ThemeKey | None = None
    header_style: HeaderStyle | None = None
    logo_align: LogoAlign | None = None
    button_shape: ButtonShape | None = None
    font: FontKey | None = None
    show_details: bool | None = None
    signature: _Narrow | None = None
    footer_text: _Footer | None = None
    tagline: _Tagline | None = None


class EmailDesignPreview(EmailDesignUpdate):
    sample: Literal["document", "message"] = "document"


def _clean_text(value: Any, limit: int) -> str:
    from app.honesty import optional_honest_narrative

    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return optional_honest_narrative(text, label="email design text", max_length=limit) or ""


def normalize(raw: Any, *, platform: bool) -> dict[str, Any]:
    """A full, safe style from whatever is stored (unknown keys and bad values fall back)."""
    base = dict(PLATFORM_DEFAULT if platform else TENANT_DEFAULT)
    if not isinstance(raw, dict):
        return base
    allowed = {
        "theme": set(THEMES),
        "header_style": {"solid", "light", "minimal"},
        "logo_align": {"left", "center"},
        "button_shape": set(BUTTON_RADIUS),
        "font": set(FONTS),
    }
    for key, values in allowed.items():
        if key in base and raw.get(key) in values:
            base[key] = raw[key]
    if "show_details" in base and isinstance(raw.get("show_details"), bool):
        base["show_details"] = raw["show_details"]
    for key, limit in (("signature", 200), ("footer_text", 300), ("tagline", 80)):
        if key in base and key in raw:
            value = str(raw.get(key) or "").strip()[:limit]
            base[key] = value
    return base


def merged(current: dict[str, Any], payload: dict[str, Any], *, platform: bool) -> dict[str, Any]:
    """Apply a validated update; text fields pass the narrative honesty check (400 on garbage)."""
    out = normalize(current, platform=platform)
    for key, value in payload.items():
        if key not in out:
            continue  # e.g. header_style on the owner's layout
        if key in ("signature", "footer_text", "tagline"):
            limit = {"signature": 200, "footer_text": 300, "tagline": 80}[key]
            out[key] = _clean_text(value, limit)
        elif value is not None:
            out[key] = value
    return out


def is_platform_tenant(tenant: Any | None) -> bool:
    if tenant is None:
        return True
    from app.tenants import PROTECTED_TENANT_SLUGS

    return str(getattr(tenant, "slug", "") or "") in PROTECTED_TENANT_SLUGS


def stored_style(tenant: Any | None) -> dict[str, Any]:
    """The style this tenant's emails use (the owner's cached style when there is no tenant)."""
    if tenant is None:
        return platform_style()
    raw = getattr(tenant, "print_branding", None) or {}
    if not isinstance(raw, dict):
        raw = {}
    platform = is_platform_tenant(tenant)
    return normalize(raw.get(PLATFORM_KEY if platform else TENANT_KEY), platform=platform)


# ---- The owner's style, kept in memory so mail with no tenant can use it ----
_PLATFORM_CACHE: dict[str, Any] = {"style": None, "at": 0.0}
_PLATFORM_TTL = 60.0


def platform_style() -> dict[str, Any]:
    return normalize(_PLATFORM_CACHE.get("style"), platform=True)


def set_platform_style(style: dict[str, Any] | None) -> None:
    _PLATFORM_CACHE["style"] = dict(style) if style else None
    _PLATFORM_CACHE["at"] = time.monotonic()


def reset_platform_cache_for_tests() -> None:
    _PLATFORM_CACHE["style"] = None
    _PLATFORM_CACHE["at"] = 0.0


async def refresh_platform_style(*, force: bool = False) -> dict[str, Any]:
    """Re-read the owner's style at most once a minute per process (workers stay in step)."""
    if not force and _PLATFORM_CACHE["at"] and time.monotonic() - _PLATFORM_CACHE["at"] < _PLATFORM_TTL:
        return platform_style()
    try:
        from sqlalchemy import select

        from app import models as m
        from app.db import SessionLocal
        from app.tenants import PROTECTED_TENANT_SLUGS

        bind = getattr(SessionLocal, "kw", {}).get("bind")
        if bind is not None and bind.dialect.name == "sqlite":
            # SQLite (tests, single-file dev) shares one connection between sessions, so
            # closing this read would roll back the caller's unsaved work. Saving the
            # design fills the cache directly instead.
            _PLATFORM_CACHE["at"] = time.monotonic()
            return platform_style()
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(m.Tenant.print_branding).where(m.Tenant.slug.in_(sorted(PROTECTED_TENANT_SLUGS)))
                )
            ).scalars().all()
        found = next(
            (r.get(PLATFORM_KEY) for r in rows if isinstance(r, dict) and r.get(PLATFORM_KEY)),
            None,
        )
        if found is not None or not _PLATFORM_CACHE["style"]:
            set_platform_style(found)
        else:
            _PLATFORM_CACHE["at"] = time.monotonic()
    except Exception:  # mail must still go out with the defaults
        _PLATFORM_CACHE["at"] = time.monotonic()
    return platform_style()


def save(tenant_row: Any, style: dict[str, Any], *, platform: bool) -> None:
    current = dict(getattr(tenant_row, "print_branding", None) or {})
    current[PLATFORM_KEY if platform else TENANT_KEY] = style
    tenant_row.print_branding = current  # new dict so the JSON column is marked changed
    if platform:
        set_platform_style(style)


def options() -> dict[str, Any]:
    """What the designer screen offers."""
    return {
        "themes": [
            {"key": key, "label": t["label"], "header": t["header"], "line": t["line"], "button": t["button"]}
            for key, t in THEMES.items()
        ],
        "header_styles": [
            {"key": "solid", "label": "Colour band"},
            {"key": "light", "label": "Light"},
            {"key": "minimal", "label": "Minimal"},
        ],
        "logo_aligns": [{"key": "left", "label": "Left"}, {"key": "center", "label": "Centre"}],
        "button_shapes": [
            {"key": "rounded", "label": "Rounded"},
            {"key": "pill", "label": "Pill"},
            {"key": "square", "label": "Square"},
        ],
        "fonts": [
            {"key": "modern", "label": "Modern"},
            {"key": "classic", "label": "Classic serif"},
            {"key": "system", "label": "Plain"},
        ],
    }


def sample_body(kind: str, *, company: str, currency: str = "GHS") -> tuple[str, str]:
    """Title and inner HTML for the designer preview."""
    from app import emailer
    from app.print_branding import document_table_html

    if kind == "message":
        inner = (
            f"<p>Hello {company},</p>"
            "<p>Here is a short update to show how your messages look. Links like "
            '<a href="https://example.com">this one</a> take your colour.</p>'
            + emailer.email_button("https://example.com", "Open Ribdigi ERP")
            + "<p>Reply to this email if you have any questions.</p>"
        )
        return "A message from us", inner
    rows = "".join(
        emailer._doc_line_row(name, str(qty), f"{currency} {price:.2f}", f"{currency} {qty * price:.2f}")
        for name, qty, price in (("Rice 5kg", 3, 120.0), ("Cooking oil 1L", 6, 35.5))
    )
    inner = (
        emailer._doc_meta_block(
            f"From <strong>{company}</strong><br/>To Kofi Mensah Stores<br/>Invoice date 12/11/2026"
            "<br/>Payment due date 26/11/2026"
        )
        + document_table_html(headers=["Item", "Qty", "Price", "Line"], rows_html=rows)
        + emailer._doc_totals_block(
            [f"Subtotal: {currency} 573.00", f"Tax: {currency} 85.95"],
            total_line=f"Total: {currency} 658.95",
        )
    )
    return "Sales Invoice INV-2026-0042", inner
