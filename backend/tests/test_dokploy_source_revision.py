"""Dokploy production images must identify the git revision and migrate once."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOKPLOY = ROOT / "docker-compose.dokploy.yml"
STAMP = ROOT / "backend" / "ribdigi-build-id.txt"
FRONTEND_STAMP = ROOT / "frontend" / "ribdigi-build-id.txt"
DOCKERFILE = ROOT / "backend" / "Dockerfile"
ENTRYPOINT = ROOT / "backend" / "scripts" / "docker-entrypoint.sh"
BOOTSTRAP = ROOT / "backend" / "scripts" / "bootstrap.py"
ROOT_IGNORE = ROOT / ".dockerignore"
BACKEND_IGNORE = ROOT / "backend" / ".dockerignore"
RESOLVER = ROOT / "backend" / "scripts" / "resolve_source_revision.py"

STALE = {
    "20261003-live-test-store-scope",
    "20261008-alembic-single-head-0136",
}


def _load_resolver():
    spec = importlib.util.spec_from_file_location("resolve_source_revision", RESOLVER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stamp() -> str:
    return next(line.strip() for line in STAMP.read_text(encoding="utf-8").splitlines() if line.strip())


def _git_short_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_stamp_is_a_source_revision_not_a_static_label():
    """Stamp is a git sha. After these files are committed, HEAD moves and the
    stamp may be that commit's parent; the image id still comes from .git.
    """
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs git and the repository's .git directory")
    stamp = _stamp()
    head = _git_short_head()
    assert len(stamp) == 12
    assert all(ch in "0123456789abcdef" for ch in stamp)
    assert stamp not in STALE
    assert FRONTEND_STAMP.read_text(encoding="utf-8").strip() == stamp
    if stamp != head:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", stamp, "HEAD"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert ancestor.returncode == 0, "build stamp is neither HEAD nor an ancestor of HEAD"


def test_resolver_uses_git_head_and_refuses_stale_labels(tmp_path: Path):
    resolver = _load_resolver()
    git_dir = tmp_path / "git"
    ref = git_dir / "refs" / "heads" / "production"
    ref.parent.mkdir(parents=True)
    ref.write_text("aaaaaaaaaaaa111111111111aaaaaaaaaaaa1111\n", encoding="utf-8")
    (git_dir / "HEAD").write_text("ref: refs/heads/production\n", encoding="utf-8")
    assert resolver.resolve_source_revision("f35f5653b651", git_dir, "f35f5653b651") == "aaaaaaaaaaaa"

    pointer = tmp_path / "worktree-git"
    pointer.write_text("gitdir: /outside/the/context\n", encoding="utf-8")
    assert resolver.resolve_source_revision("f35f5653b651", pointer, "f35f5653b651") == "f35f5653b651"

    try:
        resolver.resolve_source_revision("20261003-live-test-store-scope", pointer, "f35f5653b651")
    except SystemExit:
        pass
    else:
        raise AssertionError("stale build label was accepted")


def test_dokploy_compose_builds_from_this_checkout_and_migrate_does_not_loop():
    text = DOKPLOY.read_text(encoding="utf-8")
    stamp = _stamp()
    image = f"image: ribdigi-backend:{stamp}"
    assert text.count(image) == 4
    assert "context: ./backend" not in text
    assert text.count("context: .") >= 4
    assert text.count("dockerfile: backend/Dockerfile") == 4
    assert text.count("pull_policy: build") == 5
    frontend = text.split("\n  frontend:\n", 1)[1].split("\n  backend:\n", 1)[0]
    assert "pull_policy: build" in frontend
    assert text.count(f'RIBDIGI_SOURCE_REV: "{stamp}"') == 4
    assert "20261008-alembic-single-head-0136" not in text.split("test ")[0]
    assert 'restart: "no"' in text
    assert "restart: on-failure" not in text.split("minio-init")[0]
    assert "service_completed_successfully" in text
    assert "postgres_data:/var/lib/postgresql/data" in text
    assert "POSTGRES_DB: ${POSTGRES_DB:-ribdigi_erp}" in text
    migrate = text.split("  migrate:", 1)[1].split("  celery_worker:", 1)[0]
    assert 'restart: "no"' in migrate
    assert "alembic upgrade head" not in migrate
    assert 'test "$$HEADS" = "20261011_0138 (head)"' in migrate
    assert "20261008-alembic-single-head-0136" in migrate
    assert 'test "$$BUILD_ID" != "20261008-alembic-single-head-0136"' in migrate
    backend = text.split("\n  backend:\n", 1)[1].split("\n  migrate:\n", 1)[0]
    assert "\n      migrate:\n" in backend
    assert "service_completed_successfully" in backend


def test_dockerignore_keeps_alembic_versions_and_build_id():
    root_ignore = ROOT_IGNORE.read_text(encoding="utf-8")
    backend_ignore = BACKEND_IGNORE.read_text(encoding="utf-8")
    for text in (root_ignore, backend_ignore):
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                continue
            assert "alembic/versions" not in stripped
            assert "ribdigi-build-id" not in stripped
    assert "Dockerfile" not in {
        line.strip() for line in backend_ignore.splitlines() if line.strip() and not line.strip().startswith("#")
    }
    root_ignored = {
        line.strip()
        for line in root_ignore.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("!")
    }
    for kept in (".git", ".git/HEAD", ".git/refs", ".git/packed-refs"):
        assert kept not in root_ignored
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY backend/ribdigi-build-id.txt /tmp/ribdigi-build-id.txt" in dockerfile
    assert "COPY .git /tmp/dotgit" in dockerfile
    assert "COPY backend/alembic ./alembic" in dockerfile
    assert "ENV RIBDIGI_BUILD_ID=" not in dockerfile
    entry = ENTRYPOINT.read_text(encoding="utf-8")
    assert "export RIBDIGI_BUILD_ID" in entry
    assert "FATAL missing $BUILD_ID_FILE" in entry
    assert "20261003-live-test-store-scope" in entry
    local_compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "RIBDIGI_ALLOW_MISSING_BUILD_ID" in local_compose
    assert "RIBDIGI_ALLOW_MISSING_BUILD_ID" not in DOKPLOY.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"upgrade", "head"' in bootstrap
    assert '"upgrade", "heads"' not in bootstrap
    assert "refusing create_all fallback" in bootstrap
