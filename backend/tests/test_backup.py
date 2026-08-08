import gzip
import hashlib
import json

from app.backup import encrypt_payload, decrypt_archive, FORMAT_NAME


def test_encrypt_decrypt_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.backup.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))

    payload = {
        "format": FORMAT_NAME,
        "version": 1,
        "tenant_id": "tenant-1",
        "tenant": {"company_name": "Acme"},
        "datasets": {"products": [{"id": "p1", "tenant_id": "tenant-1", "name": "Widget"}]},
    }
    file_bytes, file_checksum, plain_checksum = encrypt_payload(payload)
    assert len(file_checksum) == 64
    assert len(plain_checksum) == 64
    assert hashlib.sha256(file_bytes).hexdigest() == file_checksum

    restored = decrypt_archive(file_bytes, expected_file_checksum=file_checksum)
    assert restored["tenant_id"] == "tenant-1"
    assert restored["datasets"]["products"][0]["name"] == "Widget"


def test_checksum_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("app.backup.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    payload = {"format": FORMAT_NAME, "version": 1, "tenant_id": "t", "datasets": {}}
    file_bytes, file_checksum, _ = encrypt_payload(payload)
    try:
        decrypt_archive(file_bytes, expected_file_checksum="0" * 64)
        assert False, "expected checksum failure"
    except Exception as exc:
        assert "checksum" in str(exc.detail).lower()


def test_tampered_ciphertext_rejected(monkeypatch):
    monkeypatch.setattr("app.backup.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    payload = {"format": FORMAT_NAME, "version": 1, "tenant_id": "t", "datasets": {}}
    file_bytes, _, _ = encrypt_payload(payload)
    envelope = json.loads(file_bytes.decode("utf-8"))
    envelope["ciphertext_b64"] = envelope["ciphertext_b64"][:-4] + "AAAA"
    bad = json.dumps(envelope, sort_keys=True).encode("utf-8")
    try:
        decrypt_archive(bad)
        assert False, "expected decrypt failure"
    except Exception as exc:
        assert "decrypt" in str(exc.detail).lower() or "Unable" in str(exc.detail)


def test_gzip_payload_is_compressed(monkeypatch):
    monkeypatch.setattr("app.backup.settings.JWT_SECRET_KEY", "unit-test-secret-key-32chars!!")
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    big = {
        "format": FORMAT_NAME,
        "version": 1,
        "tenant_id": "t",
        "datasets": {"x": [{"n": i} for i in range(200)]},
    }
    file_bytes, _, plain_checksum = encrypt_payload(big)
    envelope = json.loads(file_bytes.decode("utf-8"))
    assert envelope["plain_sha256"] == plain_checksum
    raw = json.dumps(big, sort_keys=True).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() != plain_checksum
    assert hashlib.sha256(gzip.compress(raw, compresslevel=6, mtime=0)).hexdigest() == plain_checksum
