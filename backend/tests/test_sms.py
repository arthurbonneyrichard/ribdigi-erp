import asyncio

from app import sms as sms_svc
from app.config import settings


def test_normalize_phone_e164_and_local():
    assert sms_svc.normalize_phone("+233 24 123 4567") == "+233241234567"
    assert sms_svc.normalize_phone("0241234567") == "0241234567"
    assert sms_svc.normalize_phone("") is None
    assert sms_svc.normalize_phone("12") is None


def test_sms_console_mode_when_twilio_missing(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "")
    sms_svc.clear_dev_outbox()

    result = asyncio.run(sms_svc.send_sms(to="+233241234567", body="hello"))
    assert result.sent is True
    assert result.mode == "console"
    assert sms_svc.get_dev_outbox()


def test_sms_disabled(monkeypatch):
    monkeypatch.setattr(settings, "SMS_ENABLED", False)

    result = asyncio.run(sms_svc.send_sms(to="+233241234567", body="hello"))
    assert result.sent is False
    assert result.mode == "disabled"


def test_sms_status_shape():
    status = sms_svc.sms_status()
    assert "enabled" in status
    assert "mode" in status
    assert "configured" in status
