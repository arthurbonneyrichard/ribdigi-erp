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


@pytest.mark.asyncio
async def test_verification_email_content():
    result = await emailer.send_verification_email(
        to="a@example.com", token="abc", company_name="Acme"
    )
    assert result.sent is True
    body = emailer.get_dev_outbox()[0]["text_body"]
    assert "Acme" in body
    assert "verify-email" in body


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
