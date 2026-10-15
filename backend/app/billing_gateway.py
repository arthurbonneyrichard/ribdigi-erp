"""SaaS subscription gateway adapter.

`mock` is the sandbox used by tests and local development. It never talks to a
live processor. `paystack` and `flutterwave` charge only when that provider's
secret is set. Any other named gateway uses the public address the software
owner saves. Empty credentials do not pretend a charge succeeded.

Card numbers, CVV, PINs, and banking passwords are not accepted or stored.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from app.config import settings

CONSENT_VERSION = "saas-billing-v1"
BILLING_PROVIDERS = frozenset({"mock", "paystack", "flutterwave"})
LIVE_CHARGE_PROVIDERS = frozenset({"paystack", "flutterwave"})
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{2,31}$")
_BLOCKED_GATEWAY_HOSTS = frozenset({
    "localhost",
    "host.docker.internal",
    "metadata.google.internal",
})
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
        tenant_id: str | None = None,
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
        tenant_id: str | None = None,
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
        tenant_id: str | None = None,
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
        tenant_id: str | None = None,
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
        tenant_id: str | None = None,
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
        company = _company_metadata(tenant_id)
        if company:
            payload["metadata"] = company
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
        tenant_id: str | None = None,
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
        company = _company_metadata(tenant_id)
        if company:
            payload["metadata"] = company
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


def _company_metadata(tenant_id: str | None) -> dict | None:
    """Echo the company id so a later webhook can prove which tenant was charged."""
    company = str(tenant_id or "").strip()
    if not company:
        return None
    return {"tenant_id": company}


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
        tenant_id: str | None = None,
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
        company = _company_metadata(tenant_id)
        if company:
            payload["meta"] = company
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
        tenant_id: str | None = None,
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
        company = _company_metadata(tenant_id)
        if company:
            payload["meta"] = company
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


def normalize_billing_provider(value: str) -> str:
    """Built-in providers, or another gateway name made of letters, numbers, and hyphens."""
    name = (value or "").strip().lower()
    if name in BILLING_PROVIDERS or _PROVIDER_RE.match(name):
        return name
    raise HTTPException(
        status_code=422,
        detail="Enter a gateway name using letters, numbers, and hyphens",
    )


def is_custom_billing_provider(provider: str) -> bool:
    name = (provider or "").strip().lower()
    return bool(_PROVIDER_RE.match(name)) and name not in BILLING_PROVIDERS


class CustomGateway(BillingGateway):
    """Hosted checkout for a gateway the software owner names.

    Connection test calls GET {base}/health and does not create a charge.
    Checkout calls POST {base}/checkout. A plan is paid only after a signed webhook.
    """

    def __init__(self, *, provider: str, secret: str, base_url: str) -> None:
        self.provider = normalize_billing_provider(provider)
        self.secret = (secret or "").strip()
        self.base_url = validate_custom_base_url(base_url)

    def configured(self) -> bool:
        return bool(self.secret and self.base_url)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json"}

    def _public_host(self) -> bool:
        host = (urlparse(self.base_url).hostname or "").lower()
        try:
            answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False
        seen = False
        for answer in answers:
            address = answer[4][0]
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                return False
            seen = True
            if not ip.is_global:
                return False
        return seen

    def test_connection(self) -> tuple[bool, str]:
        if not self.configured():
            return False, "gateway_not_configured"
        if not self._public_host():
            return False, "provider_url_rejected"
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=15.0,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            return False, "gateway_unreachable"
        if 200 <= response.status_code < 300:
            return True, "gateway_ok"
        return False, "gateway_rejected"

    def charge(
        self,
        *,
        authorization_ref: str,
        amount_minor: int,
        currency: str,
        reference: str,
        email: str,
        tenant_id: str | None = None,
    ) -> ChargeResult:
        if not self.configured():
            return ChargeResult(False, None, "gateway_not_configured")
        token = (authorization_ref or "").strip()
        if token.startswith("gw_"):
            token = token[3:]
        if not token:
            return ChargeResult(False, None, "invalid_authorization")
        payload = {
            "authorization_ref": token,
            "amount": _major_amount(amount_minor),
            "amount_minor": int(amount_minor),
            "currency": (currency or "").strip().upper(),
            "reference": reference,
            "email": email,
        }
        company = _company_metadata(tenant_id)
        if company:
            payload["metadata"] = company
        try:
            response = httpx.post(
                f"{self.base_url}/charge",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
                follow_redirects=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return ChargeResult(False, None, "gateway_unreachable")
        data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else body
        if not isinstance(data, dict):
            return ChargeResult(False, None, "gateway_rejected")
        status = str(data.get("status") or "").strip().lower()
        ref = str(data.get("reference") or data.get("id") or reference)
        if response.status_code < 300 and status in {"success", "successful", "approved"}:
            return ChargeResult(True, ref, "approved")
        if status in {"pending", "processing", "ongoing"}:
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
        tenant_id: str | None = None,
    ) -> CheckoutResult:
        if not self.configured():
            return CheckoutResult(False, None, reference, "gateway_not_configured")
        payload = {
            "email": email,
            "amount": _major_amount(amount_minor),
            "amount_minor": int(amount_minor),
            "currency": (currency or "").strip().upper(),
            "reference": reference,
            "callback_url": callback_url,
        }
        company = _company_metadata(tenant_id)
        if company:
            payload["metadata"] = company
        try:
            response = httpx.post(
                f"{self.base_url}/checkout",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
                follow_redirects=False,
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return CheckoutResult(False, None, reference, "gateway_unreachable")
        data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else {}
        link = ""
        if isinstance(body, dict):
            link = str(body.get("checkout_url") or body.get("payment_url") or "")
        if isinstance(data, dict) and not link:
            link = str(data.get("checkout_url") or data.get("authorization_url") or data.get("link") or data.get("payment_url") or "")
        if response.status_code >= 300 or not link.startswith("https://"):
            return CheckoutResult(False, None, reference, "gateway_rejected")
        return CheckoutResult(True, link, reference, "hosted_checkout")


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


def validate_custom_base_url(url: str) -> str:
    """Public HTTPS address only. Private, local, and credentialed hosts are rejected."""
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Gateway address must be https with no credentials")
    if parsed.query or parsed.fragment or (parsed.port not in (None, 443)):
        raise HTTPException(status_code=422, detail="Gateway address is not allowed")
    if (
        not host
        or host in _BLOCKED_GATEWAY_HOSTS
        or host.endswith(".local")
        or host.endswith(".internal")
        or ".." in (parsed.path or "")
    ):
        raise HTTPException(status_code=422, detail="Gateway host is not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if not re.match(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$", host):
            raise HTTPException(status_code=422, detail="Gateway host is not allowed")
    else:
        if not ip.is_global:
            raise HTTPException(status_code=422, detail="Gateway host is not allowed")
    path = (parsed.path or "").rstrip("/")
    return f"https://{host}{path}"


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
    if is_custom_billing_provider(name):
        return CustomGateway(provider=name, secret=secret, base_url=base_url or "")
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


def _normalize_custom_webhook(event: dict) -> dict:
    """Keep the charge.success contract and reject card-shaped tokens."""
    if not isinstance(event, dict):
        return event
    data = event.get("data")
    if not isinstance(data, dict):
        return event
    data = dict(data)

    def _token(code: str) -> str:
        text = (code or "").strip()
        compact = text.replace(" ", "").replace("-", "")
        if not text or _TOKEN_CARD_RE.search(compact):
            return ""
        if text.startswith(("AUTH_", "mock_auth_", "flw_", "gw_")):
            return text
        return f"gw_{text}"

    nested = data.get("authorization")
    if isinstance(nested, dict):
        nested = dict(nested)
        code = _token(str(nested.get("authorization_code") or ""))
        if code:
            nested["authorization_code"] = code
        else:
            nested["authorization_code"] = ""
            nested["reusable"] = False
        data["authorization"] = nested
    elif data.get("authorization_code"):
        data["authorization_code"] = _token(str(data.get("authorization_code") or ""))
    return {**event, "data": data}


def normalize_webhook_event(provider: str, event: dict) -> dict:
    """Map a provider payload onto the charge.success / charge.failed contract.

    Paystack already uses that contract and is returned unchanged. Flutterwave
    sends major-unit amounts and charge.completed.
    """
    name = (provider or "").strip().lower()
    if is_custom_billing_provider(name):
        return _normalize_custom_webhook(event)
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
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
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
            "tenant_id": data.get("tenant_id") or meta.get("tenant_id"),
            "authorization": {"authorization_code": token, "reusable": True} if token else {},
            "customer": {"customer_code": customer_code} if customer_code else {},
        },
    }
