"""Security control 09: responses do not advertise the stack or echo internals."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.http_errors import register_exception_handlers, safe_validation_detail
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def _client():
    return TestClient(app, raise_server_exceptions=False)


def test_422_does_not_echo_submitted_values():
    secret = "Sup3r-Secret-Pass!"
    r = _client().post("/api/v1/auth/login", json={"email": "not-an-email", "password": secret})
    assert r.status_code == 422
    assert secret not in r.text
    for err in r.json()["detail"]:
        assert set(err) <= {"type", "loc", "msg"}
        assert "loc" in err and "msg" in err


def test_422_malformed_json_hides_parser_context():
    r = _client().post(
        "/api/v1/auth/login",
        content="{bad",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert "input" not in r.text and "ctx" not in r.text


def test_safe_validation_detail_keeps_only_public_keys():
    out = safe_validation_detail(
        [{"type": "missing", "loc": ("body", "x", 0), "msg": "Field required", "input": {"p": 1}, "url": "https://errors.pydantic.dev/x", "ctx": {"error": ValueError("e")}}]
    )
    assert out == [{"type": "missing", "loc": ["body", "x", 0], "msg": "Field required"}]


def test_500_is_generic_without_traceback():
    probe = FastAPI()
    register_exception_handlers(probe)

    @probe.get("/boom")
    def boom():
        raise RuntimeError("secret path /app/app/internal.py postgres://user:pw@db:5432")

    r = TestClient(probe, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    body = r.text
    for leak in ("Traceback", "RuntimeError", "/app/", "postgres://", "internal.py"):
        assert leak not in body


def test_no_technology_headers_from_app():
    c = _client()
    for path in ("/api/v1/health", "/api/v1/does-not-exist"):
        r = c.get(path)
        lowered = {k.lower() for k in r.headers}
        assert "x-powered-by" not in lowered
        assert "server" not in lowered


def test_every_uvicorn_launch_hides_server_header():
    files = [
        ROOT / "backend" / "Dockerfile",
        ROOT / "docker-compose.dokploy.yml",
        ROOT / "docker-compose.prod.yml",
        ROOT / "docker-compose.yml",
        ROOT / "helm" / "ribdigi" / "values.yaml",
        ROOT / "k8s" / "backend.yaml",
    ]
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "uvicorn app.main:app" in line and not line.lstrip().startswith("#"):
                # Folded YAML commands continue on the next lines.
                command = " ".join(lines[i : i + 5])
                assert "--no-server-header" in command, f"{f.name}: {line.strip()}"


def test_frontend_starts_through_header_filter():
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["node", "serve.cjs"]' in dockerfile
    serve = (ROOT / "frontend" / "serve.cjs").read_text(encoding="utf-8")
    assert "x-nextjs-cache" in serve and "TRACE" in serve
    config = (ROOT / "frontend" / "next.config.mjs").read_text(encoding="utf-8")
    assert "poweredByHeader: false" in config


def test_unmatched_hosts_get_plain_404_not_traefik_page():
    compose = (ROOT / "docker-compose.dokploy.yml").read_text(encoding="utf-8")
    block = compose.split("\n  nohost:", 1)[1].split("\n  backend:", 1)[0]
    assert "s.end('Not Found')" in block
    for router in ("ribdigi-nohost-web", "ribdigi-nohost-websecure"):
        assert f"traefik.http.routers.{router}.priority=1" in block
        assert f"traefik.http.routers.{router}.service=ribdigi-nohost" in block
    # Never published on the host; Traefik reaches it on the Dokploy network only.
    assert "ports:" not in block
