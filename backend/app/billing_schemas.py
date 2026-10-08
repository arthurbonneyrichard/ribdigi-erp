"""Request bodies for SaaS subscription billing. extra=forbid."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BillingConsentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=2, max_length=40)
    accept: bool


class BillingCheckoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=2, max_length=40)


class BillingSandboxAuthorizeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_code: str = Field(min_length=8, max_length=160)


class BillingCancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool


class BillingPlanWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=40)
    package_code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    interval: str = Field(min_length=4, max_length=16)
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    trial_days: int = 14
    grace_days: int = 7
    is_active: bool = True


class BillingPlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    interval: str | None = None
    trial_days: int | None = None
    grace_days: int | None = None
    is_active: bool | None = None


class BillingAssignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=2, max_length=40)
    trial_ends_at: str | None = None
    next_renewal_at: str | None = None


class BillingManualPaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    reference: str = Field(min_length=2, max_length=100)
    note: str | None = None
