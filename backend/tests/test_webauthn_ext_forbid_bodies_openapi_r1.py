"""OpenAPI honesty tips #541–#546: WebAuthn ext/transports + extra=forbid bodies."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AuthenticatorTransportListValue,
    LineItem,
    Login,
    NotificationPreferencesUpdate,
    OpeningStockCreate,
    PosSaleCreate,
    SalesInvoiceItemCreate,
    StockAdjust,
    StockCountCancel,
    StockCountCreate,
    StockCountItemsUpdate,
    StockMove,
    StockOut,
    WebAuthnAttestationResponse,
    WebAuthnClientExtensionResultsValue,
    WebAuthnRegistrationCredential,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_REG_CRED = {
    "id": "cred-id",
    "rawId": "cred-id",
    "type": "public-key",
    "response": {
        "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
        "attestationObject": "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YQ",
        "transports": ["internal", "USB", "cable"],
    },
    "clientExtensionResults": {"credProps": {"rk": True}},
}

_transports = TypeAdapter(AuthenticatorTransportListValue)
_ext = TypeAdapter(WebAuthnClientExtensionResultsValue)


def test_webauthn_ext_transports_and_forbid_schema():
    assert _transports.validate_python(["USB", "cable", "internal"]) == [
        "usb",
        "hybrid",
        "internal",
    ]
    for bad in ("usb", ["fly"], ["usb", "!!!"], [1], {"usb": True}):
        with pytest.raises(ValidationError):
            _transports.validate_python(bad)

    assert _ext.validate_python(None) == {}
    assert _ext.validate_python({"credProps": {"rk": True}})["credProps"]["rk"] is True
    for bad in ([], "x", 1, True):
        with pytest.raises(ValidationError):
            _ext.validate_python(bad)
    with pytest.raises(ValidationError):
        _ext.validate_python({f"k{i}": i for i in range(33)})

    cred = WebAuthnRegistrationCredential.model_validate(_REG_CRED)
    assert cred.response.transports == ["internal", "usb", "hybrid"]
    with pytest.raises(ValidationError):
        WebAuthnAttestationResponse.model_validate(
            {
                "clientDataJSON": "x",
                "attestationObject": "y",
                "transports": ["unknown-bus"],
            }
        )
    with pytest.raises(ValidationError):
        WebAuthnRegistrationCredential.model_validate(
            {**_REG_CRED, "clientExtensionResults": ["nope"]}
        )

    Login.model_validate(
        {"email": "a@b.co", "password": "SecurePass123!", "tenant_id": "alpha"}
    )
    with pytest.raises(ValidationError):
        Login.model_validate(
            {
                "email": "a@b.co",
                "password": "SecurePass123!",
                "tenant_id": "alpha",
                "evil": 1,
            }
        )

    StockCountCreate.model_validate({"warehouse_id": str(uuid4())})
    with pytest.raises(ValidationError):
        StockCountCreate.model_validate(
            {"warehouse_id": str(uuid4()), "evil": True}
        )
    with pytest.raises(ValidationError):
        StockCountItemsUpdate.model_validate(
            {
                "items": [
                    {"product_id": str(uuid4()), "counted_qty": 1, "extra": 1}
                ]
            }
        )
    with pytest.raises(ValidationError):
        StockCountCancel.model_validate({"reason": "Wrong warehouse", "x": 1})

    LineItem.model_validate({"product_id": str(uuid4()), "quantity": 1})
    with pytest.raises(ValidationError):
        LineItem.model_validate(
            {"product_id": str(uuid4()), "quantity": 1, "poison": True}
        )
    with pytest.raises(ValidationError):
        SalesInvoiceItemCreate.model_validate(
            {"product_id": str(uuid4()), "quantity": 1, "poison": True}
        )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": [
                    {
                        "product_id": str(uuid4()),
                        "quantity": 1,
                        "poison": True,
                    }
                ]
            }
        )

    StockAdjust.model_validate({"quantity": -1, "reason": "damage"})
    with pytest.raises(ValidationError):
        StockAdjust.model_validate(
            {"quantity": -1, "reason": "damage", "evil": 1}
        )
    StockMove.model_validate({"product_id": str(uuid4()), "quantity": 1})
    with pytest.raises(ValidationError):
        StockMove.model_validate(
            {"product_id": str(uuid4()), "quantity": 1, "evil": 1}
        )
    StockOut.model_validate(
        {
            "product_id": str(uuid4()),
            "quantity": 1,
            "reference_type": "sale",
        }
    )
    with pytest.raises(ValidationError):
        StockOut.model_validate(
            {
                "product_id": str(uuid4()),
                "quantity": 1,
                "reference_type": "sale",
                "evil": 1,
            }
        )
    OpeningStockCreate.model_validate(
        {"lines": [{"product_id": str(uuid4()), "quantity": 1}]}
    )
    with pytest.raises(ValidationError):
        OpeningStockCreate.model_validate(
            {
                "lines": [{"product_id": str(uuid4()), "quantity": 1}],
                "evil": 1,
            }
        )

    NotificationPreferencesUpdate.model_validate(
        {"preferences": {"low_stock": {"email": True}}}
    )
    with pytest.raises(ValidationError):
        NotificationPreferencesUpdate.model_validate(
            {"preferences": {"low_stock": {"email": True}}, "evil": 1}
        )


def test_webauthn_ext_forbid_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "WebAuthn clientExtensionResults OpenAPI",
        "WebAuthn transports OpenAPI",
        "Stock count bodies OpenAPI",
        "Auth session bodies OpenAPI",
        "Sale line bodies OpenAPI",
        "Inventory stock mutation + notification prefs OpenAPI",
    ):
        assert title in agents, title
    assert "WebAuthnClientExtensionResultsValue" in agents
    assert "AuthenticatorTransportListValue" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AuthenticatorTransportListValue" in docs
    assert "WebAuthnClientExtensionResultsValue" in docs
    assert "extra=forbid" in docs
    assert "StockCountItemsUpdate" in docs

    sec = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "credentialToJson" in sec
    assert "smart-card" in sec
    assert "cable" in sec
    assert "clientExtensionResults" in sec

    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Save count lines"' in inv


@pytest.mark.asyncio
async def test_webauthn_ext_forbid_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
            "evil": True,
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/auth/webauthn/register/verify",
        headers=headers,
        json={
            "credential": {
                **_REG_CRED,
                "response": {
                    **_REG_CRED["response"],
                    "transports": ["telepathy"],
                },
            },
            "name": "X",
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/auth/webauthn/register/verify",
        headers=headers,
        json={
            "credential": {**_REG_CRED, "clientExtensionResults": "nope"},
            "name": "X",
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": str(uuid4()), "evil": 1},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.patch(
        f"/api/v1/notifications/settings",
        headers=headers,
        json={"preferences": {}, "evil": 1},
    )
    assert resp.status_code == 422, resp.text
