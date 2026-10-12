"""SaaS subscription gateway adapter.

`mock` is the sandbox used by tests and local development. It never talks to a
live processor. `paystack` and `flutterwave` charge only when that provider's
secret is set. Empty credentials do not pretend a charge succeeded.

Card numbers, CVV, PINs, and banking passwords are not accepted or stored.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from app.config import settings

CONSENT_VERSION = "saas-billing-v1"
BILLING_PROVIDERS = frozenset({"mock", "paystack", "flutterwave"})
LIVE_CHARGE_PROVIDERS = frozenset({"paystack", "flutterwave"})
PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_CHARGE_URL = "https://api.paystack.co/transaction/charge_authorization"


@dataclass
class ChargeResult:
    ok: bool
    gateway_reference: str | None
    message: str
    authorization_ref: str | None = None
    customer_ref: str | None = None
    pending: bool = False


@dataclass
class CheckoutResult:
    ok: bool
    checkout_url: str | None
    reference: str
    message: str


class BillingGateway:
    provider = "unconfigured"

    def configured(self) -> bool:
        return False

    def charge(
        self,
        *,
        authorization_ref: str,
        amount_minor: int,
        currency: str,
        reference: str,
        email: str,
    ) -> ChargeResult:
        return ChargeResult(False, None, "Billing provider is not configured")

    def checkout(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str,
    ) -> CheckoutResult:
        return CheckoutResult(False, None, reference, "Billing provider is not configured")


class MockGateway(BillingGateway):
    """In-process sandbox. Disabled when APP_ENV is production."""

    provider = "mock"
    _charged: set[str] = set()

    def __init__(self, *, mode: str = "sandbox") -> None:
        self.mode = (mode or "sandbox").strip().lower()

    def configured(self) -> bool:
        if settings.APP_ENV.lower() == "production":
            return False
        return self.mode != "live"

    def test_connection(self) -> tuple[bool, str]:
        """Confirm sandbox mock is usable. Does not capture a payment."""
        if settings.APP_ENV.lower() == "production":
            return False, "sandbox_disabled"
        if self.mode == "live":
            return False, "mock_live_refused"
        return True, "sandbox_ready"

    def charge(
        self,
        *,
        authorization_ref: str,
        amount_minor: int,
        currency: str,
        reference: str,
        email: str,
    ) -> ChargeResult:
        if not self.configured():
            return ChargeResult(False, None, "sandbox_disabled")
        if amount_minor <= 0 or not currency:
            return ChargeResult(False, None, "invalid_amount")
        token = (authorization_ref or "").strip()
        if not token.startswith("mock_auth_"):
            return ChargeResult(False, None, "invalid_authorization")
        if token.startswith("mock_auth_fail"):
            return ChargeResult(False, None, "declined")
        if reference in self._charged:
            return ChargeResult(True, f"mock_tx_{reference}", "already_charged")
        self._charged.add(reference)
        return ChargeResult(True, f"mock_tx_{reference}", "approved")

    def checkout(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str,
    ) -> CheckoutResult:
        if not self.configured():
            return CheckoutResult(False, None, reference, "sandbox_disabled")
        base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
        return CheckoutResult(
            True,
            f"{base}/company/billing?checkout_ref={reference}",
            reference,
            "sandbox_checkout",
        )


class PaystackGateway(BillingGateway):
    provider = "paystack"

    def __init__(self, *, secret: str | None = None, base_url: str | None = None) -> None:
        raw = settings.PAYSTACK_SECRET_KEY if secret is None else secret
        self.secret = (raw or "").strip()
        self.base_url = (base_url or "https://api.paystack.co").strip().rstrip("/")

    def configured(self) -> bool:
        return bool(self.secret)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> tuple[bool, str]:
        """Read Paystack balance. This does not create a charge."""
        if not self.configured():
            return False, "paystack_not_configured"
        if not self.base_url.startswith("https://api.paystack.co"):
            return False, "provider_url_rejected"
        try:
            response = httpx.get(f"{self.base_url}/balance", headers=self._headers(), timeout=15.0)
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return False, "paystack_unreachable"
        if response.status_code < 300 and isinstance(body, dict) and body.get("status") is True:
            return True, "paystack_ok"
        return False, "paystack_rejected"

    def charge(
        self,
        *,
        authorization_ref: str,
        amount_minor: int,
        currency: str,
        reference: str,
        email: str,
    ) -> ChargeResult:
        if not self.configured():
            return ChargeResult(False, None, "paystack_not_configured")
        payload = {
            "authorization_code": authorization_ref,
            "email": email,
            "amount": int(amount_minor),
            "currency": currency,
            "reference": reference,
        }
        try:
            response = httpx.post(
                f"{self.base_url}/transaction/charge_authorization",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return ChargeResult(False, None, "paystack_unreachable")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return ChargeResult(False, None, "paystack_rejected")
        status = str(data.get("status") or "").lower()
        ref = str(data.get("reference") or reference)
        if response.status_code < 300 and body.get("status") and status == "success":
            auth = data.get("authorization") if isinstance(data.get("authorization"), dict) else {}
            customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
            return ChargeResult(
                True,
                ref,
                "approved",
                authorization_ref=str(auth.get("authorization_code") or "") or None,
                customer_ref=str(customer.get("customer_code") or "") or None,
            )
        if status in {"pending", "ongoing", "processing"}:
            return ChargeResult(False, ref, "pending", pending=True)
        return ChargeResult(False, ref, "declined")

    def checkout(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str,
    ) -> CheckoutResult:
        if not self.configured():
            return CheckoutResult(False, None, reference, "paystack_not_configured")
        payload = {
            "email": email,
            "amount": int(amount_minor),
            "currency": currency,
            "reference": reference,
            "callback_url": callback_url,
        }
        try:
            response = httpx.post(
                f"{self.base_url}/transaction/initialize",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return CheckoutResult(False, None, reference, "paystack_unreachable")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or not data.get("authorization_url"):
            return CheckoutResult(False, None, reference, "paystack_rejected")
        return CheckoutResult(True, str(data["authorization_url"]), reference, "hosted_checkout")


_FLUTTERWAVE_COUNTRY = {
    "GHS": "GH",
    "NGN": "NG",
    "USD": "US",
    "KES": "KE",
    "ZAR": "ZA",
    "GBP": "GB",
}


def _major_amount(amount_minor: int):
    major = (Decimal(int(amount_minor)) / Decimal("100")).quantize(Decimal("0.01"))
    return int(major) if major == major.to_integral_value() else float(major)


class FlutterwaveGateway(BillingGateway):
    """Hosted Flutterwave checkout. A charge is recorded only after a signed webhook."""

    provider = "flutterwave"

    def __init__(self, *, secret: str | None = None, base_url: str | None = None) -> None:
        raw = settings.FLUTTERWAVE_SECRET_KEY if secret is None else secret
        self.secret = (raw or "").strip()
        self.base_url = (base_url or "https://api.flutterwave.com").strip().rstrip("/")

    def configured(self) -> bool:
        return bool(self.secret)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> tuple[bool, str]:
        """Read the balance list. This does not create a charge."""
        if not self.configured():
            return False, "flutterwave_not_configured"
        if not self.base_url.startswith("https://api.flutterwave.com"):
            return False, "provider_url_rejected"
        try:
            response = httpx.get(
                f"{self.base_url}/v3/balances",
                headers=self._headers(),
                timeout=15.0,
                follow_redirects=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return False, "flutterwave_unreachable"
        if response.status_code < 300 and isinstance(body, dict) and str(body.get("status") or "").lower() == "success":
            return True, "flutterwave_ok"
        return False, "flutterwave_rejected"

    def charge(
        self,
        *,
        authorization_ref: str,
        amount_minor: int,
        currency: str,
        reference: str,
        email: str,
    ) -> ChargeResult:
        if not self.configured():
            return ChargeResult(False, None, "flutterwave_not_configured")
        code = (currency or "").strip().upper()
        country = _FLUTTERWAVE_COUNTRY.get(code)
        token = (authorization_ref or "").strip()
        if token.startswith("flw_"):
            token = token[4:]
        if not country or not token:
            return ChargeResult(False, None, "invalid_authorization")
        payload = {
            "token": token,
            "currency": code,
            "country": country,
            "amount": _major_amount(amount_minor),
            "email": email,
            "tx_ref": reference,
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v3/tokenized-charges",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
                follow_redirects=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return ChargeResult(False, None, "flutterwave_unreachable")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return ChargeResult(False, None, "flutterwave_rejected")
        status = str(data.get("status") or "").lower()
        ref = str(data.get("flw_ref") or data.get("tx_ref") or reference)
        if response.status_code < 300 and str(body.get("status") or "").lower() == "success" and status == "successful":
            return ChargeResult(True, ref, "approved")
        if status in {"pending", "pending-capture"}:
            return ChargeResult(False, ref, "pending", pending=True)
        return ChargeResult(False, ref, "declined")

    def checkout(
        self,
        *,
        email: str,
        amount_minor: int,
        currency: str,
        reference: str,
        callback_url: str,
    ) -> CheckoutResult:
        if not self.configured():
            return CheckoutResult(False, None, reference, "flutterwave_not_configured")
        payload = {
            "tx_ref": reference,
            "amount": _major_amount(amount_minor),
            "currency": (currency or "").strip().upper(),
            "redirect_url": callback_url,
            "customer": {"email": email},
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v3/payments",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
                follow_redirects=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return CheckoutResult(False, None, reference, "flutterwave_unreachable")
        data = body.get("data") if isinstance(body, dict) else None
        link = data.get("link") if isinstance(data, dict) else None
        if not link:
            return CheckoutResult(False, None, reference, "flutterwave_rejected")
        return CheckoutResult(True, str(link), reference, "hosted_checkout")


def get_gateway() -> BillingGateway:
    provider = (settings.BILLING_PROVIDER or "mock").strip().lower()
    if provider == "mock":
        return MockGateway()
    if provider == "paystack":
        return PaystackGateway()
    if provider == "flutterwave":
        return FlutterwaveGateway()
    return BillingGateway()


def verify_webhook_signature(
    provider: str, body: bytes, header: str | None, secret: str | None = None
) -> bool:
    supplied = (header or "").strip()
    if not supplied or not body:
        return False
    name = (provider or "").strip().lower()
    if name == "paystack":
        key = settings.PAYSTACK_SECRET_KEY if secret is None else secret
        key = (key or "").strip()
        if not key:
            return False
        digest = hmac.new(key.encode("utf-8"), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(digest, supplied)
    if name == "flutterwave":
        if secret is None:
            key = (settings.FLUTTERWAVE_WEBHOOK_HASH or settings.BILLING_WEBHOOK_SECRET or "").strip()
        else:
            key = (secret or "").strip()
        if not key:
            return False
        if hmac.compare_digest(key, supplied):
            return True
        digest = hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, supplied)
    key = settings.BILLING_WEBHOOK_SECRET if secret is None else secret
    secret_key = (key or "").strip()
    if not secret_key:
        return False
    digest = hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, supplied)


def sign_mock_webhook(body: bytes) -> str:
    secret = (settings.BILLING_WEBHOOK_SECRET or "").strip().encode("utf-8")
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def minor_units(amount: Decimal) -> int:
    quantized = amount.quantize(Decimal("0.01"))
    return int((quantized * Decimal("100")).to_integral_value())


def webhook_json(body: bytes) -> dict:
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("webhook body must be an object")
    return parsed


PAYSTACK_HOST = "api.paystack.co"
FLUTTERWAVE_HOST = "api.flutterwave.com"
_TOKEN_CARD_RE = re.compile(r"\d(?:[ -]?\d){12,18}")


def validate_paystack_base_url(url: str) -> str:
    """Allow only the public Paystack API host over HTTPS."""
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Provider URL must be https with no credentials")
    if parsed.query or parsed.fragment or (parsed.port not in (None, 443)):
        raise HTTPException(status_code=422, detail="Provider URL is not allowed")
    if host != PAYSTACK_HOST:
        raise HTTPException(status_code=422, detail="Provider host is not allowed")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(status_code=422, detail="Provider host is not allowed")
    return f"https://{host}"


def validate_flutterwave_base_url(url: str) -> str:
    """Allow only the public Flutterwave API host over HTTPS."""
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Provider URL must be https with no credentials")
    if parsed.query or parsed.fragment or (parsed.port not in (None, 443)):
        raise HTTPException(status_code=422, detail="Provider URL is not allowed")
    if host != FLUTTERWAVE_HOST:
        raise HTTPException(status_code=422, detail="Provider host is not allowed")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(status_code=422, detail="Provider host is not allowed")
    return f"https://{host}"


def gateway_for_config(*, provider: str, mode: str, secret: str, base_url: str | None) -> BillingGateway:
    name = (provider or "").strip().lower()
    if name == "mock":
        return MockGateway(mode=mode)
    if name == "paystack":
        base = validate_paystack_base_url(base_url or "https://api.paystack.co")
        return PaystackGateway(secret=secret, base_url=base)
    if name == "flutterwave":
        base = validate_flutterwave_base_url(base_url or "https://api.flutterwave.com")
        return FlutterwaveGateway(secret=secret, base_url=base)
    return BillingGateway()


async def current_gateway(db) -> BillingGateway:
    """Use a tested, enabled platform row. Otherwise keep the environment gateway."""
    from sqlalchemy import select

    from app import models as m
    from app.billing_secrets import decrypt_billing_secret

    row = (await db.execute(select(m.PlatformBillingGateway).limit(1))).scalar_one_or_none()
    if row is None:
        return get_gateway()
    if not row.enabled or not row.last_test_ok or not row.secret_enc:
        return BillingGateway()
    try:
        secret = decrypt_billing_secret(row.secret_enc)
    except HTTPException:
        return BillingGateway()
    return gateway_for_config(
        provider=row.provider,
        mode=row.mode,
        secret=secret,
        base_url=row.api_base_url,
    )


async def webhook_signing_secret(db, provider: str) -> str | None:
    """Stored secret when a row exists. None means use the environment secret."""
    from sqlalchemy import select

    from app import models as m
    from app.billing_secrets import decrypt_billing_secret

    row = (await db.execute(select(m.PlatformBillingGateway).limit(1))).scalar_one_or_none()
    if row is None or (row.provider or "").strip().lower() != (provider or "").strip().lower():
        return None
    name = (provider or "").strip().lower()
    token = row.secret_enc if name == "paystack" else row.webhook_secret_enc
    if not token:
        return None
    try:
        return decrypt_billing_secret(token)
    except HTTPException:
        return ""


def normalize_webhook_event(provider: str, event: dict) -> dict:
    """Map a provider payload onto the charge.success / charge.failed contract.

    Paystack already uses that contract and is returned unchanged. Flutterwave
    sends major-unit amounts and charge.completed.
    """
    name = (provider or "").strip().lower()
    if name != "flutterwave" or not isinstance(event, dict):
        return event
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    status = str(data.get("status") or "").strip().lower()
    raw = str(event.get("event") or event.get("event.type") or "").strip().lower()
    if raw in {"charge.completed", "charge.success"} and status in {"successful", "success"}:
        mapped = "charge.success"
    elif status in {"failed", "cancelled", "canceled", "voided"} or raw == "charge.failed":
        mapped = "charge.failed"
    else:
        mapped = raw or "ignored"
    amount = data.get("amount")
    minor = None
    if amount is not None and str(amount).strip() != "":
        try:
            minor = minor_units(Decimal(str(amount)))
        except Exception:
            minor = -1
    card = data.get("card") if isinstance(data.get("card"), dict) else {}
    raw_token = str(card.get("token") or "").strip()
    compact = raw_token.replace(" ", "").replace("-", "")
    token = None
    if raw_token and not _TOKEN_CARD_RE.search(compact):
        token = raw_token if raw_token.startswith("flw_") else f"flw_{raw_token}"
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    customer_code = str(customer.get("customer_code") or customer.get("id") or "").strip()
    return {
        "id": event.get("id") or data.get("id"),
        "event": mapped,
        "data": {
            "id": data.get("id"),
            "reference": str(data.get("tx_ref") or data.get("reference") or "").strip(),
            "amount": minor,
            "currency": data.get("currency"),
            "status": "success" if mapped == "charge.success" else status,
            "gateway_reference": str(data.get("flw_ref") or data.get("id") or ""),
            "tenant_id": data.get("tenant_id"),
            "authorization": {"authorization_code": token, "reusable": True} if token else {},
            "customer": {"customer_code": customer_code} if customer_code else {},
        },
    }
