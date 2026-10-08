"""SaaS subscription gateway adapter.

`mock` is the sandbox used by tests and local development. It never talks to a
live processor. `paystack` charges only when `PAYSTACK_SECRET_KEY` is set.
Empty credentials do not pretend a charge succeeded.

Card numbers, CVV, PINs, and banking passwords are not accepted or stored.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.config import settings

CONSENT_VERSION = "saas-billing-v1"
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

    def configured(self) -> bool:
        return settings.APP_ENV.lower() != "production"

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

    def configured(self) -> bool:
        return bool((settings.PAYSTACK_SECRET_KEY or "").strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY.strip()}",
            "Content-Type": "application/json",
        }

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
                PAYSTACK_CHARGE_URL,
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
                PAYSTACK_INITIALIZE_URL,
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


def get_gateway() -> BillingGateway:
    provider = (settings.BILLING_PROVIDER or "mock").strip().lower()
    if provider == "mock":
        return MockGateway()
    if provider == "paystack":
        return PaystackGateway()
    return BillingGateway()


def verify_webhook_signature(provider: str, body: bytes, header: str | None) -> bool:
    supplied = (header or "").strip()
    if not supplied or not body:
        return False
    name = (provider or "").strip().lower()
    if name == "paystack":
        secret = (settings.PAYSTACK_SECRET_KEY or "").strip()
        if not secret:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(digest, supplied)
    secret = (settings.BILLING_WEBHOOK_SECRET or "").strip()
    if not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
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
