"""Stage 99 C1 — Purchase Request-to-GRN pipeline discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_pr_po_grn_and_notification_fix():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Purchase Requests" in shell
    assert "Pending PRs" in shell
    assert "pr_status=pending" in shell
    assert "Purchase Orders" in shell
    assert "Open POs" in shell
    assert "po_status=open" in shell
    assert "GRN" in shell
    assert "/purchasing?tab=grn" in shell
    dash = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "purchase_order" in dash
    assert "/purchasing?tab=orders" in dash
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "prStatusFilter" in purchasing
    assert "poStatusFilter" in purchasing
    assert "grnStatusFilter" in purchasing


@pytest.mark.asyncio
async def test_pr_po_grn_status_filter_api(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    assert (await ac.get("/api/v1/purchasing/requests?status=bogus", headers=headers)).status_code == 400
    assert (await ac.get("/api/v1/purchasing/orders?status=bogus", headers=headers)).status_code == 400
    assert (await ac.get("/api/v1/purchasing/grn?status=bogus", headers=headers)).status_code == 400

    pending = await ac.get("/api/v1/purchasing/requests?status=pending", headers=headers)
    assert pending.status_code == 200, pending.text
    for row in pending.json().get("data") or []:
        assert row["status"] == "pending"

    open_pos = await ac.get("/api/v1/purchasing/orders?status=open", headers=headers)
    assert open_pos.status_code == 200, open_pos.text
    for row in open_pos.json().get("data") or []:
        assert row["status"] in {"sent", "partially_received"}

    grns = await ac.get("/api/v1/purchasing/grn?status=posted", headers=headers)
    assert grns.status_code == 200, grns.text
    for row in grns.json().get("data") or []:
        assert row["status"] == "posted"
