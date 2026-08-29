"""Path UuidIdValue OpenAPI honesty for remaining route Path FKs (#465–#485)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)
_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"

_TITLES = (
    "Transfer path transfer_id OpenAPI",
    "Bank statement path statement_id OpenAPI",
    "Webhook path webhook_id OpenAPI",
    "Purchase request path request_id OpenAPI",
    "Purchase order path po_id OpenAPI",
    "Cheque path cheque_id OpenAPI",
    "Journal entry path entry_id OpenAPI",
    "Backup path backup_id OpenAPI",
    "COA path account_id OpenAPI",
    "Bank connection path connection_id OpenAPI",
    "Bank statement line path line_id OpenAPI",
    "Report schedule path schedule_id OpenAPI",
    "Tax rate path rate_id OpenAPI",
    "API key path key_id OpenAPI",
    "POS sale path sale_id OpenAPI",
    "Recurring expense path recurring_id OpenAPI",
    "Audit log path log_id OpenAPI",
    "WebAuthn path credential_id OpenAPI",
    "GRN path grn_id OpenAPI",
    "Webhook delivery path delivery_id OpenAPI",
    "AI report template path template_id OpenAPI",
)


def test_path_uuid_id_batch3_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "xfer_001"):
        with pytest.raises(ValidationError):
            _uuid.validate_python(bad)


def test_path_uuid_id_batch3_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in _TITLES:
        assert title in agents, title
    # Path surface exhausted except helper tenant_id
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    import re

    left = re.findall(r"^    ([a-z_]+_id): str,$", api, re.M)
    assert left == ["tenant_id"], left


@pytest.mark.asyncio
async def test_path_uuid_id_batch3_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    async def assert_bad(method: str, template: str, **kw):
        for bad in ("not-a-uuid", "!!!", "xfer_001"):
            path = template.format(bad=bad)
            resp = await getattr(ac, method)(path, headers=headers, **kw)
            assert resp.status_code == 422, (method, path, resp.text)

        missing = template.format(bad=str(uuid4()))
        resp = await getattr(ac, method)(missing, headers=headers, **kw)
        assert resp.status_code in (200, 400, 404, 405), (method, missing, resp.text)
        assert resp.status_code != 422

    await assert_bad("get", "/api/v1/accounting/transfers/{bad}")
    await assert_bad("get", "/api/v1/stores/transfers/{bad}")
    await assert_bad("get", "/api/v1/inventory/stock-transfers/{bad}")
    await assert_bad("get", "/api/v1/accounting/bank-statements/{bad}")
    await assert_bad("get", "/api/v1/webhooks/{bad}")
    await assert_bad("get", "/api/v1/purchasing/requests/{bad}")
    await assert_bad("get", "/api/v1/purchasing/orders/{bad}")
    await assert_bad("get", "/api/v1/purchasing/grn/{bad}")
    await assert_bad("get", "/api/v1/accounting/cheques/{bad}")
    await assert_bad("get", "/api/v1/backup/{bad}")
    await assert_bad("get", "/api/v1/tax/rates/{bad}")
    await assert_bad("get", "/api/v1/api-keys/{bad}")
    await assert_bad("get", "/api/v1/pos/sales/{bad}/receipt")
    await assert_bad("patch", "/api/v1/accounting/accounts/{bad}", json={"name": "X"})
    await assert_bad("patch", "/api/v1/reports/schedules/{bad}", json={"enabled": False})
    await assert_bad("patch", "/api/v1/expenses/recurring/{bad}", json={"is_active": False})
    await assert_bad(
        "patch",
        "/api/v1/accounting/bank-connections/{bad}",
        json={"display_name": "X"},
    )

    # Nested statement line + webhook delivery
    sid = str(uuid4())
    for bad in ("not-a-uuid", "!!!", "line_001"):
        resp = await ac.post(
            f"/api/v1/accounting/bank-statements/{sid}/lines/{bad}/match",
            headers=headers,
            json={"journal_line_id": str(uuid4())},
        )
        assert resp.status_code == 422, resp.text

    wid = str(uuid4())
    for bad in ("not-a-uuid", "!!!", "del_001"):
        resp = await ac.post(
            f"/api/v1/webhooks/{wid}/deliveries/{bad}/retry",
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    for bad in ("not-a-uuid", "!!!", "tpl_001"):
        resp = await ac.delete(
            f"/api/v1/ai/reports/templates/{bad}",
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    for bad in ("not-a-uuid", "!!!", "cred_001"):
        resp = await ac.delete(
            f"/api/v1/auth/webauthn/credentials/{bad}",
            headers=headers,
        )
        assert resp.status_code == 422, resp.text

    for bad in ("not-a-uuid", "!!!", "log_001"):
        resp = await ac.delete(f"/api/v1/audit-logs/{bad}", headers=headers)
        assert resp.status_code == 422, resp.text

    for bad in ("not-a-uuid", "!!!", "je_001"):
        resp = await ac.post(
            f"/api/v1/accounting/journal-entries/{bad}/unpost",
            headers=headers,
        )
        assert resp.status_code == 422, resp.text
