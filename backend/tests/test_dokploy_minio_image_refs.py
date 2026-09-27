"""Dokploy MinIO images must be anonymously pullable (not quay.io / docker.io/minio)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOKPLOY = ROOT / "docker-compose.dokploy.yml"

MINIO_IMAGE = (
    "docker.io/bitnamilegacy/minio:2024.12.18"
    "@sha256:c0ede65eb88e47138470202c517bacf55ab3c27df848030b7b46e69d34b7d192"
)
MC_IMAGE = (
    "docker.io/bitnamilegacy/minio-client:2024.11.21"
    "@sha256:a7786f5e6bb7b7080fd142a9f4eec0b7f713d246b5ebdbe0ff55f3d5d9c315bb"
)


def test_dokploy_compose_pins_public_minio_images():
    text = DOKPLOY.read_text(encoding="utf-8")
    image_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("image:")
    ]
    assert not any("quay.io/" in line for line in image_lines)
    assert not any("image: minio/minio:" in line or "image: minio/mc:" in line for line in image_lines)
    assert MINIO_IMAGE in text
    assert MC_IMAGE in text
    assert "command: server /data --console-address :9001" in text
    assert "minio_data:/data" in text
    assert "http://minio:9000" in text
    assert "MINIO_ROOT_USER" in text
    assert "MINIO_ROOT_PASSWORD" in text
    assert "S3_BUCKET" in text
