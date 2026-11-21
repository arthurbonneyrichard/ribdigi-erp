"""Gym member files and the printable membership card."""

from __future__ import annotations

import base64
from datetime import date

import pytest
from sqlalchemy import select

from app import gym, gym_files
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell

# A real 1x1 PNG.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _up(name="p.png", data=PNG, ctype="image/png"):
    return {"file": (name, data, ctype)}


@pytest.mark.asyncio
async def test_photo_is_replaced_files_are_listed_and_downloadable_and_junk_is_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    url = f"/api/v1/gym/members/{member['id']}/files"
    first = await ac.post(url, headers=h, data={"kind": "photo"}, files=_up())
    assert first.status_code == 200, first.text
    second = await ac.post(url, headers=h, data={"kind": "photo"}, files=_up("q.png"))
    assert second.status_code == 200
    listed = (await ac.get(url, headers=h)).json()["data"]
    assert [f["kind"] for f in listed] == ["photo"] and listed[0]["id"] == second.json()["data"]["id"]  # one profile photo
    got = await ac.get(f"/api/v1/gym/files/{listed[0]['id']}", headers=h)
    assert got.status_code == 200 and got.content == PNG
    assert (await ac.post(url, headers=h, data={"kind": "photo"}, files=_up("x.png", b"not an image", "image/png"))).status_code == 400
    assert (await ac.post(url, headers=h, data={"kind": "photo"}, files=_up("x.exe", PNG, "application/x-msdownload"))).status_code == 400
    assert (await ac.post(url, headers=h, data={"kind": "photo"}, files=_up("e.png", b"", "image/png"))).status_code == 400
    assert (await ac.post(url, headers=h, data={"kind": "selfie"}, files=_up())).status_code == 422
    assert (await ac.delete(f"/api/v1/gym/files/{listed[0]['id']}", headers=h)).status_code == 200
    assert (await ac.get(url, headers=h)).json()["data"] == []


@pytest.mark.asyncio
async def test_a_pdf_waiver_is_accepted_but_a_photo_must_be_an_image(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    url = f"/api/v1/gym/members/{member['id']}/files"
    ok = await ac.post(url, headers=h, data={"kind": "waiver"}, files=_up("waiver.pdf", PDF, "application/pdf"))
    assert ok.status_code == 200, ok.text
    assert (await ac.post(url, headers=h, data={"kind": "photo"}, files=_up("w.pdf", PDF, "application/pdf"))).status_code == 400
    assert (await ac.post(url, headers=h, data={"kind": "progress_photo"}, files=_up())).status_code == 200


def test_who_sees_which_kind_of_file():
    def kinds(role):
        out = set()
        for kind, area in gym_files.KINDS.items():
            try:
                gym.job({"role": role}, area)
                out.add(kind)
            except Exception:  # noqa: BLE001
                pass
        return out

    assert kinds("gym_frontdesk") == {"photo", "id_document", "waiver"}
    assert kinds("gym_trainer") == {"progress_photo"}
    assert len(kinds("company_admin")) == 4


@pytest.mark.asyncio
async def test_printed_card_shows_the_member_and_replaces_the_last_card(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    await ac.post(f"/api/v1/gym/members/{member['id']}/files", headers=h, data={"kind": "photo"}, files=_up())
    r = await ac.post(f"/api/v1/gym/members/{member['id']}/card", headers=h)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert member["full_name"] in r.text and "data:image/png;base64," in r.text and "Door QR code" in r.text
    assert (await ac.post(f"/api/v1/gym/members/{member['id']}/card", headers=h)).status_code == 200
    live = (
        await db_session.execute(select(m.GymCredential).where(m.GymCredential.label == "printed card", m.GymCredential.status == "active"))
    ).scalars().all()
    assert len(live) == 1  # a reprint cancels the earlier card


@pytest.mark.asyncio
async def test_files_are_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-1", full_name="Theirs", joined_on=date.today())
    db_session.add(other)
    await db_session.commit()
    theirs = m.GymMemberFile(
        tenant_id=seed["t2"].id, member_id=other.id, kind="photo", storage_key="x/y.png", filename="y.png", content_type="image/png", size_bytes=1
    )
    db_session.add(theirs)
    await db_session.commit()
    assert (await ac.post(f"/api/v1/gym/members/{other.id}/files", headers=h, data={"kind": "photo"}, files=_up())).status_code == 404
    assert (await ac.get(f"/api/v1/gym/members/{other.id}/files", headers=h)).status_code == 404
    assert (await ac.get(f"/api/v1/gym/files/{theirs.id}", headers=h)).status_code == 404
    assert (await ac.delete(f"/api/v1/gym/files/{theirs.id}", headers=h)).status_code == 404
    assert (await ac.post(f"/api/v1/gym/members/{other.id}/card", headers=h)).status_code == 404
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get(f"/api/v1/gym/members/{other.id}/files", headers=h)).status_code == 403
