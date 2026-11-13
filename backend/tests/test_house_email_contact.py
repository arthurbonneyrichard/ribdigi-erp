"""Ribdigi House emails carry the wide House logo and the telephone and WhatsApp lines."""

from __future__ import annotations

from app import emailer


def test_house_email_has_logo_and_contact_lines():
    out = emailer.render_branded_html(body_html="<p>Hello</p>", title="Hi", tenant=None, allow_platform_logo=True)
    assert "ribdigi-house-logo" in out
    assert 'href="tel:+233302944376"' in out and "+233 30 294 4376" in out
    assert 'href="https://wa.me/233530537307"' in out and "+233 53 053 7307" in out


def test_house_logo_is_the_wide_mark():
    _data, _kind, width, height = emailer._platform_house_logo_bytes()
    assert width == 220 and width / height > 3
