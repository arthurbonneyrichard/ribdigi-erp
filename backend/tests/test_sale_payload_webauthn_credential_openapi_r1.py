"""OpenAPI honesty tips #536–#540: sale payload bags + WebAuthn credentials."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    EmailTestRequest,
    LegacyTransactionPayload,
    PosSaleCreate,
    TransactionCreate,
    WebAuthnAuthenticationCredential,
    WebAuthnLoginVerify,
    WebAuthnRegisterVerify,
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
    },
}
_ASSERT_CRED = {
    "id": "cred-id",
    "rawId": "cred-id",
    "type": "public-key",
    "response": {
        "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0In0",
        "authenticatorData": "authenticator-data",
        "signature": "signature-bytes",
        "userHandle": None,
    },
}


def test_sale_payload_and_webauthn_credential_schema():
    LegacyTransactionPayload.model_validate({})
    LegacyTransactionPayload.model_validate(
        {"items": [{"product_id": str(uuid4()), "quantity": 1}]}
    )
    with pytest.raises(ValidationError):
        LegacyTransactionPayload.model_validate({"evil": True})
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"payload": {"evil": 1}})
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"unknown": 1})

    PosSaleCreate.model_validate(
        {"items": [{"product_id": str(uuid4()), "quantity": 1}]}
    )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": [{"product_id": str(uuid4()), "quantity": 1}],
                "payload": {},
            }
        )
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": [{"product_id": str(uuid4()), "quantity": 1}],
                "extra_field": True,
            }
        )

    WebAuthnRegistrationCredential.model_validate(_REG_CRED)
    with pytest.raises(ValidationError):
        WebAuthnRegistrationCredential.model_validate({"id": "x"})
    with pytest.raises(ValidationError):
        WebAuthnRegisterVerify.model_validate(
            {"credential": _REG_CRED, "evil": 1}
        )

    WebAuthnAuthenticationCredential.model_validate(_ASSERT_CRED)
    WebAuthnLoginVerify.model_validate(
        {"challenge_token": "tok.tok.tok", "credential": _ASSERT_CRED}
    )
    with pytest.raises(ValidationError):
        WebAuthnAuthenticationCredential.model_validate(
            {"id": "x", "rawId": "x", "type": "public-key", "response": {}}
        )

    EmailTestRequest.model_validate({})
    with pytest.raises(ValidationError):
        EmailTestRequest.model_validate({"to": "a@b.co", "cc": "x"})


def test_sale_payload_webauthn_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Legacy sale payload OpenAPI",
        "POS sale payload OpenAPI",
        "WebAuthn credential OpenAPI",
        "Email test body OpenAPI",
    ):
        assert title in agents, title
    assert "LegacyTransactionPayload" in agents
    assert "WebAuthnRegistrationCredential" in agents

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "LegacyTransactionPayload" in docs
    assert "WebAuthnRegistrationCredential" in docs
    assert "EmailTestRequest" in docs
    assert "no client `payload`" in docs or "no client `payload` bag" in docs

    sec = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Passkey name"' in sec
    assert "type: cred.type" in sec
    assert "credentialToJson" in sec
    assert "clientExtensionResults" in sec

    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "const body: Record<string, unknown>" in pos
    sale_body = pos.split("const body: Record<string, unknown>")[1].split("};")[0]
    assert "payload" not in sale_body


@pytest.mark.asyncio
async def test_sale_payload_webauthn_api_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    resp = await ac.post(
        "/api/v1/sales",
        headers=headers,
        json={"payload": {"evil": True}, "items": []},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
            "payload": {"discount_amount": 999},
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/auth/webauthn/register/verify",
        headers=headers,
        json={"credential": {"id": "only-id"}, "name": "X"},
    )
    assert resp.status_code == 422, resp.text

    resp = await ac.post(
        "/api/v1/settings/email/test",
        headers=headers,
        json={"to": "a@b.co", "evil": 1},
    )
    assert resp.status_code == 422, resp.text
