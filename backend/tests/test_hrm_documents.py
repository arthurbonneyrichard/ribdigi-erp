"""Staff documents: HR files them, staff open their own and accept policies by typing their name;
confidential files stay with HR managers."""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from app import storage as storage_svc
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _file(name="contract.pdf"):
    return {"file": (name, _pdf(), "application/pdf")}


async def test_staff_file_policy_and_confidential(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    ama = await _person(ac, h, email="ama@alpha.example.com", full_name="Ama Mensah")
    await _person(ac, h, email="kofi@alpha.example.com", full_name="Kofi Owusu")
    ama_h = await _login_staff(ac, h, "ama@alpha.example.com", "Ama Mensah")
    kofi_h = await _login_staff(ac, h, "kofi@alpha.example.com", "Kofi Owusu")

    contract = await ac.post(
        f"/api/v1/hrm/employees/{ama['id']}/documents", headers=h, files=_file(),
        data={"title": "Employment contract", "kind": "contract", "needs_ack": "true"},
    )
    assert contract.status_code == 200, contract.text
    contract = contract.json()["data"]
    medical = (
        await ac.post(
            f"/api/v1/hrm/employees/{ama['id']}/documents", headers=h, files=_file("note.pdf"),
            data={"title": "Medical note", "kind": "letter", "confidential": "true"},
        )
    ).json()["data"]
    policy = (await ac.post("/api/v1/hrm/documents", headers=h, files=_file("handbook.pdf"), data={"title": "Staff handbook"})).json()["data"]
    assert policy["company_wide"] and policy["needs_ack"]

    mine = {d["title"]: d for d in (await ac.get("/api/v1/hrm/me/documents", headers=ama_h)).json()["data"]}
    assert set(mine) == {"Employment contract", "Staff handbook"}  # the medical note is not shown to her
    assert (await ac.get(f"/api/v1/hrm/documents/{medical['id']}/file", headers=ama_h)).status_code == 404
    assert (await ac.get(f"/api/v1/hrm/documents/{contract['id']}/file", headers=ama_h)).status_code == 200
    assert (await ac.get(f"/api/v1/hrm/documents/{contract['id']}/file", headers=kofi_h)).status_code == 404
    assert (await ac.get(f"/api/v1/hrm/documents/{medical['id']}/file", headers=h)).status_code == 200
    # Staff cannot file documents.
    assert (await ac.post("/api/v1/hrm/documents", headers=ama_h, files=_file(), data={"title": "Mine"})).status_code == 403

    wrong = await ac.post(f"/api/v1/hrm/me/documents/{policy['id']}/accept", headers=ama_h, json={"typed_name": "Ama"})
    assert wrong.status_code == 422
    ok = await ac.post(f"/api/v1/hrm/me/documents/{policy['id']}/accept", headers=ama_h, json={"typed_name": "  ama   mensah "})
    assert ok.status_code == 200 and ok.json()["data"]["accepted_at"]
    who = {r["name"]: r["accepted_at"] for r in (await ac.get(f"/api/v1/hrm/documents/{policy['id']}/accepted", headers=h)).json()["data"]}
    assert who["Ama Mensah"] and who["Kofi Owusu"] is None
    assert any(n["title"] == "Document to read" for n in (await ac.get("/api/v1/notifications?category=hr", headers=kofi_h)).json()["data"])

    assert (await ac.post(f"/api/v1/hrm/documents/{policy['id']}/archive", headers=h)).status_code == 200
    assert {d["title"] for d in (await ac.get("/api/v1/hrm/me/documents", headers=kofi_h)).json()["data"]} == set()
