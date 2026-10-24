"""Company logo: cached/versioned sidebar endpoint, downscaled copy, CID email logo."""

from __future__ import annotations

import io
from pathlib import Path

import pyotp
import pytest
from PIL import Image

from app import emailer, logo_media
from tests.conftest import auth_headers
from tests.test_po_email import _seed_io


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _png(size: tuple[int, int], color=(30, 140, 60, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def media_dir(tmp_path, monkeypatch):
    root = tmp_path / "media"
    monkeypatch.setattr("app.config.settings.MEDIA_DIR", str(root))
    monkeypatch.setattr("app.storage.settings.MEDIA_DIR", str(root))
    logo_media.clear_caches()
    yield root
    logo_media.clear_caches()


@pytest.fixture
def console_mail(monkeypatch):
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "noreply@localhost")
    emailer.clear_dev_outbox()
    yield
    emailer.clear_dev_outbox()


async def _upload(ac, headers, data: bytes):
    r = await ac.post(
        "/api/v1/tenants/me/logo",
        headers=headers,
        files={"file": ("logo.png", data, "image/png")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_logo_endpoint_cache_headers_etag_304_and_tenant_scope(client, db_session, media_dir):
    ac, seed = client
    admin = await _super(ac, seed)
    uploaded = await _upload(ac, admin, _png((64, 32)))
    version = uploaded["logo_version"]
    assert version and len(version) == 16

    me = (await ac.get("/api/v1/me", headers=admin)).json()["data"]
    assert me["has_logo"] is True
    assert me["logo_version"] == version

    plain = await ac.get("/api/v1/tenants/me/logo", headers=admin)
    assert plain.status_code == 200
    assert plain.headers["etag"] == f'"{version}"'
    assert plain.headers["cache-control"] == "private, no-cache"
    assert "Authorization" in plain.headers["vary"]

    versioned = await ac.get("/api/v1/tenants/me/logo", headers=admin, params={"v": version})
    assert versioned.status_code == 200
    assert versioned.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert versioned.content == plain.content

    not_modified = await ac.get(
        "/api/v1/tenants/me/logo", headers={**admin, "If-None-Match": f'"{version}"'}
    )
    assert not_modified.status_code == 304
    assert not_modified.content == b""
    assert not_modified.headers["etag"] == f'"{version}"'

    bad_v = await ac.get("/api/v1/tenants/me/logo", headers=admin, params={"v": "http://x"})
    assert bad_v.status_code == 422

    # Beta has its own logo; alpha's ETag never yields a 304 or alpha's bytes for beta.
    beta = seed["t2"]
    beta_key = f"{beta.id}/logos/betalogo.png"
    path = Path(media_dir) / beta_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png((40, 40), color=(200, 20, 20, 255)))
    beta.logo_url = beta_key
    db_session.add(beta)
    await db_session.commit()

    beta_headers = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_get = await ac.get(
        "/api/v1/tenants/me/logo", headers={**beta_headers, "If-None-Match": f'"{version}"'}
    )
    assert beta_get.status_code == 200
    beta_version = logo_media.logo_version(beta.id, beta_key)
    assert beta_get.headers["etag"] == f'"{beta_version}"'
    assert beta_version != version
    assert beta_get.content != plain.content
    with Image.open(io.BytesIO(beta_get.content)) as img:
        assert img.convert("RGB").getpixel((5, 5))[0] > 150  # red beta logo, not alpha green

    # Alpha's version query on beta's session is not treated as beta's version.
    cross = await ac.get("/api/v1/tenants/me/logo", headers=beta_headers, params={"v": version})
    assert cross.headers["cache-control"] == "private, no-cache"


@pytest.mark.asyncio
async def test_uploaded_logo_is_downscaled_and_original_kept(client, media_dir):
    ac, seed = client
    admin = await _super(ac, seed)
    big = _png((2000, 800))
    uploaded = await _upload(ac, admin, big)
    key = uploaded["logo_url"]

    original = Path(media_dir) / key
    assert original.read_bytes() == big
    display = original.with_name(original.stem + ".display.webp")
    if not display.is_file():
        display = original.with_name(original.stem + ".display.png")
    assert display.is_file()

    got = await ac.get("/api/v1/tenants/me/logo", headers=admin)
    assert got.status_code == 200
    assert got.headers["content-type"] in {"image/webp", "image/png"}
    with Image.open(io.BytesIO(got.content)) as img:
        assert max(img.size) <= logo_media.DISPLAY_MAX_PX
        assert img.size == (512, 205)
        assert img.mode in {"RGBA", "RGB"}

    # Replacing the logo removes the old original and its derivative.
    await _upload(ac, admin, _png((100, 100)))
    assert not original.exists()
    assert not display.exists()


@pytest.mark.asyncio
async def test_po_and_invoice_email_embed_logo_as_cid(client, db_session, media_dir, console_mail, monkeypatch):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io_h = await auth_headers(ac, email="io-po-email@alpha.example.com", tenant_slug="alpha")
    uploaded = await _upload(ac, admin, _png((1200, 400), color=(0, 0, 0, 0)))
    version = uploaded["logo_version"]
    cid = f"company-logo-{version}@ribdigi"

    supplier = await ac.post(
        "/api/v1/suppliers", headers=admin, json={"name": "Logo Vendor", "email": "vendor@example.com"}
    )
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io_h,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    sent = await ac.post(f"/api/v1/purchasing/orders/{po.json()['data']['id']}/send", headers=io_h)
    assert sent.status_code == 200, sent.text
    out = emailer.get_dev_outbox()[-1]
    html_body = out["html_body"]
    assert f'src="cid:{cid}"' in html_body
    assert 'alt="Alpha Co"' in html_body
    assert 'width="240" height="80"' in html_body
    assert "data:image/" not in html_body
    assert out["text_body"] and "PO-" in out["subject"]
    inline = out["inline_images"]
    assert [i["cid"] for i in inline] == [cid]
    assert inline[0]["content_type"] in {"image/png", "image/jpeg"}
    assert inline[0]["size_bytes"] < 60_000

    # Real SMTP path: inspect MIME (multipart/related with matching Content-ID).
    captured = []
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.emailer.settings.SMTP_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_FROM_EMAIL", "from@example.com")
    monkeypatch.setattr("app.emailer._smtp_send_sync", lambda msg, cfg: captured.append(msg))

    customer = await ac.post(
        "/api/v1/customers", headers=admin, json={"name": "Logo Buyer", "email": "buyer@example.com"}
    )
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": customer.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    inv_id = inv.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=admin)).status_code == 200
    sent_inv = await ac.post(f"/api/v1/sales/invoices/{inv_id}/send", headers=admin)
    assert sent_inv.status_code == 200, sent_inv.text
    assert len(captured) == 1
    msg = captured[0]
    types = [part.get_content_type() for part in msg.walk()]
    assert "multipart/related" in types
    assert "text/plain" in types and "text/html" in types
    images = [p for p in msg.walk() if p.get_content_maintype() == "image"]
    assert len(images) == 1
    assert images[0]["Content-ID"] == f"<{cid}>"
    with Image.open(io.BytesIO(images[0].get_payload(decode=True))) as img:
        assert img.size == (480, 160)  # 2× of the 240×80 header box
        # Transparent upload is flattened onto white, not black.
        assert img.convert("RGB").getpixel((10, 10)) == (255, 255, 255)
    html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    assert f"cid:{cid}" in html_part.get_content()


@pytest.mark.asyncio
async def test_document_email_without_logo_falls_back_to_company_name(client, db_session, media_dir, console_mail):
    ac, seed = client
    await _seed_io(db_session, seed)
    admin = await _super(ac, seed)
    io_h = await auth_headers(ac, email="io-po-email@alpha.example.com", tenant_slug="alpha")
    supplier = await ac.post(
        "/api/v1/suppliers", headers=admin, json={"name": "Plain Vendor", "email": "plain@example.com"}
    )
    po = await ac.post(
        "/api/v1/purchasing/orders",
        headers=io_h,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    sent = await ac.post(f"/api/v1/purchasing/orders/{po.json()['data']['id']}/send", headers=io_h)
    assert sent.status_code == 200, sent.text
    out = emailer.get_dev_outbox()[-1]
    assert "cid:" not in out["html_body"]
    assert "data:image/" not in out["html_body"]
    assert "ribdigi-email-company" in out["html_body"]
    assert "Alpha Co" in out["html_body"]
    assert "ribdigi-house-logo" not in out["html_body"]
    assert out["inline_images"] == []


def test_email_logo_is_cached_per_tenant_logo_key(media_dir, monkeypatch):
    key = "tenant-a/logos/abc.png"
    path = Path(media_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png((300, 100)))

    class _T:
        id = "tenant-a"
        logo_url = key

    reads = []
    real_read = logo_media.storage_svc.read_object

    def counting_read(k, *, tenant_id=None):
        reads.append(k)
        return real_read(k, tenant_id=tenant_id)

    monkeypatch.setattr(logo_media.storage_svc, "read_object", counting_read)
    first = logo_media.email_logo(_T())
    second = logo_media.email_logo(_T())
    assert first is second and first is not None
    assert reads == [key]
    assert (first.width, first.height) == (240, 80)


def test_foreign_tenant_cid_is_stripped_not_attached():
    emailer._register_inline("company-logo-x@ribdigi", "tenant-a", b"png", "png")
    html_in = '<p>hi</p><img class="ribdigi-email-logo" src="cid:company-logo-x@ribdigi" alt="A" />'

    class _B:
        id = "tenant-b"

    stripped, found = emailer._resolve_inline_images(html_in, _B())
    assert found == []
    assert "cid:" not in stripped and "<p>hi</p>" in stripped

    class _A:
        id = "tenant-a"

    kept, found_a = emailer._resolve_inline_images(html_in, _A())
    assert kept == html_in
    assert [c for c, _, _ in found_a] == ["company-logo-x@ribdigi"]
