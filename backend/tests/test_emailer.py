import pytest

from app import emailer


@pytest.fixture(autouse=True)
def _clear_outbox(monkeypatch):
    emailer.clear_dev_outbox()
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    yield
    emailer.clear_dev_outbox()


@pytest.mark.asyncio
async def test_console_mode_when_smtp_missing():
    result = await emailer.send_email(
        to="user@example.com",
        subject="Hello",
        text_body="Body",
    )
    assert result.sent is True
    assert result.mode == "console"
    outbox = emailer.get_dev_outbox()
    assert len(outbox) == 1
    assert outbox[0]["subject"] == "Hello"


@pytest.mark.asyncio
async def test_disabled_mode(monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", False)
    result = await emailer.send_email(to="a@example.com", subject="X", text_body="Y")
    assert result.sent is False
    assert result.mode == "disabled"


@pytest.mark.asyncio
async def test_password_reset_email_content():
    result = await emailer.send_password_reset_email(to="a@example.com", token="tok123")
    assert result.sent is True
    body = emailer.get_dev_outbox()[0]["text_body"]
    assert "tok123" in body
    assert "reset-password" in body
    html_body = emailer.get_dev_outbox()[0]["html_body"]
    assert "ribdigi-email-brand" in html_body
    assert "Password reset" in html_body


@pytest.mark.asyncio
async def test_verification_email_content():
    result = await emailer.send_verification_email(
        to="a@example.com", token="abc", company_name="Acme"
    )
    assert result.sent is True
    body = emailer.get_dev_outbox()[0]["text_body"]
    assert "Acme" in body
    assert "verify-email" in body
    html_body = emailer.get_dev_outbox()[0]["html_body"]
    assert "ribdigi-email-brand" in html_body
    assert "Acme" in html_body


@pytest.mark.asyncio
async def test_smtp_send_uses_thread(monkeypatch):
    calls = []

    def fake_send(msg, cfg):
        calls.append((msg["To"], cfg.host))

    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr("app.emailer._smtp_send_sync", fake_send)
    result = await emailer.send_email(to="to@example.com", subject="S", text_body="B")
    assert result.sent is True
    assert result.mode == "smtp"
    assert calls == [("to@example.com", "smtp.example.com")]


def test_email_status_shape():
    status = emailer.email_status()
    assert "mode" in status
    assert "configured" in status
    assert "has_password" in status
    assert "source" in status
    assert "password" not in status or status.get("password") in (None, "")


def test_render_branded_html_includes_chrome_and_escapes():
    class _T:
        company_name = "Acme <Holdings>"
        logo_url = None
        print_branding = {
            "header_text": "Run smarter & safer",
            "footer_text": "Thanks <team>",
        }

    html_body = emailer.render_branded_html(
        body_html="<p>Hello <b>world</b></p>",
        company_name="Acme <Holdings>",
        tenant=_T(),
        title="Welcome <user>",
    )
    assert "ribdigi-email-brand" in html_body
    assert "ribdigi-email-company" in html_body
    assert "Acme &lt;Holdings&gt;" in html_body
    assert "Run smarter &amp; safer" in html_body
    assert "Thanks &lt;team&gt;" in html_body
    assert "Welcome &lt;user&gt;" in html_body
    assert "<p>Hello <b>world</b></p>" in html_body
    assert "Sent via RIBDIGI ERP" in html_body


@pytest.mark.asyncio
async def test_test_email_is_branded():
    class _T:
        company_name = "Idle Demo Co"
        logo_url = None
        print_branding = {"header_text": "Demo header", "footer_text": "Demo footer"}

    result = await emailer.send_test_email(to="ops@example.com", tenant=_T())
    assert result.sent is True
    html_body = emailer.get_dev_outbox()[0]["html_body"]
    assert "ribdigi-email-brand" in html_body
    assert "Idle Demo Co" in html_body
    assert "Demo header" in html_body
    assert "Demo footer" in html_body


@pytest.mark.asyncio
async def test_invoice_email_uses_branded_shell():
    text, html_body = emailer.render_sales_invoice_bodies(
        company_name="Acme Retail",
        currency="GHS",
        customer_name="Ada",
        invoice={
            "invoice_number": "INV-1",
            "due_date": "2026-09-01",
            "items": [
                {
                    "product_id": "p1",
                    "quantity": 2,
                    "unit_price": 10,
                    "tax_rate": 0,
                    "line_total": 20,
                }
            ],
            "subtotal": 20,
            "tax_amount": 0,
            "discount_amount": 0,
            "total_amount": 20,
            "paid_amount": 0,
            "balance_due": 20,
        },
    )
    assert "INV-1" in text
    assert "ribdigi-email-brand" in html_body
    assert "Sales Invoice INV-1" in html_body
    assert "Acme Retail" in html_body
