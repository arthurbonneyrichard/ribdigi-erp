"""Stage 103 S1 — Security surface discoverability."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_security_deeplinks_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/security#passkeys" in shell
    assert "/security#totp" in shell
    assert "/security#webhooks" in shell
    assert "/security#api-keys" in shell
    assert "/security#sessions" in shell
    assert "Passkeys" in shell
    assert "Webhooks" in shell
    assert "API keys" in shell
    assert "Active sessions" in shell


def test_security_page_anchors_s1():
    security = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'id="passkeys"' in security
    assert 'id="totp"' in security
    assert 'id="webhooks"' in security
    assert 'id="api-keys"' in security
    assert 'id="sessions"' in security
    assert "scrollIntoView" in security
