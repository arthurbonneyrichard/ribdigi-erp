from pathlib import Path
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app import storage as storage_svc


class _Upload(UploadFile):
    def __init__(self, filename: str, content_type: str, data: bytes):
        super().__init__(file=BytesIO(data), filename=filename, headers={"content-type": content_type})


@pytest.mark.asyncio
async def test_save_and_open_logo(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    upload = _Upload("logo.PNG", "image/png", b"\x89PNG\r\n\x1a\nfake")
    stored = await storage_svc.save_upload(
        tenant_id="t1",
        category="logos",
        upload=upload,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=1_000_000,
    )
    assert stored.key.startswith("t1/logos/")
    assert stored.size > 0
    assert stored.backend == "local"
    path, ctype = storage_svc.open_key(stored.key, tenant_id="t1")
    assert path.is_file()
    assert ctype == "image/png"
    media = storage_svc.read_object(stored.key, tenant_id="t1")
    assert media.data.startswith(b"\x89PNG")
    assert storage_svc.delete_key(stored.key, tenant_id="t1") is True
    assert not Path(path).exists()


@pytest.mark.asyncio
async def test_rejects_bad_type(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    upload = _Upload("x.exe", "application/octet-stream", b"MZ")
    with pytest.raises(HTTPException) as exc:
        await storage_svc.save_upload(
            tenant_id="t1",
            category="logos",
            upload=upload,
            allowed_types=storage_svc.LOGO_CONTENT_TYPES,
            max_bytes=1_000_000,
        )
    assert exc.value.status_code == 400


def test_path_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    with pytest.raises(HTTPException):
        storage_svc.resolve_key("../etc/passwd", tenant_id="t1")
    with pytest.raises(HTTPException):
        storage_svc.resolve_key("other/logos/x.png", tenant_id="t1")


def test_sanitize_filename():
    assert storage_svc.sanitize_filename("../../a b.png") == "a_b.png"


@pytest.mark.asyncio
async def test_s3_backend_put_get_delete(monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage_svc.settings, "S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr(storage_svc.settings, "S3_ACCESS_KEY", "minioadmin")
    monkeypatch.setattr(storage_svc.settings, "S3_SECRET_KEY", "minioadmin")
    monkeypatch.setattr(storage_svc.settings, "S3_BUCKET", "ribdigi-test")
    monkeypatch.setattr(storage_svc.settings, "S3_FORCE_PATH_STYLE", True)
    storage_svc.reset_s3_client_cache()

    store: dict[str, bytes] = {}
    client = MagicMock()

    def put_object(**kwargs):
        store[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(**kwargs):
        key = kwargs["Key"]
        if key not in store:
            raise Exception("NoSuchKey")
        body = MagicMock()
        body.read.return_value = store[key]
        return {"Body": body, "ContentType": "image/png"}

    def delete_object(**kwargs):
        store.pop(kwargs["Key"], None)
        return {}

    def head_bucket(**kwargs):
        return {}

    client.put_object.side_effect = put_object
    client.get_object.side_effect = get_object
    client.delete_object.side_effect = delete_object
    client.head_bucket.side_effect = head_bucket

    monkeypatch.setattr(storage_svc, "_s3_client", lambda: client)

    upload = _Upload("logo.png", "image/png", b"png-bytes")
    stored = await storage_svc.save_upload(
        tenant_id="t1",
        category="logos",
        upload=upload,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=1_000_000,
    )
    assert stored.backend == "s3"
    assert stored.key in store
    media = storage_svc.read_object(stored.key, tenant_id="t1")
    assert media.data == b"png-bytes"
    assert media.backend == "s3"
    assert storage_svc.delete_key(stored.key, tenant_id="t1") is True
    assert stored.key not in store
    storage_svc.reset_s3_client_cache()


def test_storage_status_local(monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    status = storage_svc.storage_status()
    assert status["backend"] == "local"
