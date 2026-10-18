"""Platform billing UI wires Needs attention actions to owner billing APIs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BILLING_PAGE = ROOT / "frontend" / "app" / "(dashboard)" / "platform" / "billing" / "page.tsx"


def test_platform_billing_attention_ui_wires_owner_actions():
    text = BILLING_PAGE.read_text(encoding="utf-8")
    assert "/platform/billing/attention" in text
    assert "/platform/billing/tenants/" in text
    assert "/payments" in text
    assert "/retry" in text
    assert "/reactivate" in text
    assert 'aria-label="Billing attention list"' in text
    assert 'aria-label="Record manual payment ${slug}"' in text or 'Record manual payment' in text
    assert 'aria-label="Retry billing charge ${slug}"' in text or "Retry billing charge" in text
    assert 'aria-label="Restore billing access ${slug}"' in text or "Restore billing access" in text
    assert 'aria-label="Manual billing payment amount"' in text
    assert 'aria-label="Manual billing payment reference"' in text
    assert 'aria-label="Save manual billing payment"' in text
    assert "No charge was created" in text or "does not create a charge" in text
    assert "/platform/billing/tenants/" in text
    assert 'aria-label="Owner subscription invoices"' in text
