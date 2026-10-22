"""Write /app/.build-id from the git checkout baked into the image build.

Dokploy clones branch `production`, so `.git` is a directory and the id is
`git rev-parse --short=12 HEAD` of that commit. A worktree checkout only has a
gitdir pointer file; that falls back to `ribdigi-build-id.txt`, which must
itself be a 12-character sha updated from HEAD.

Stale labels such as `20261003-live-test-store-scope` are refused so a cached
layer cannot republish the image that is failing in production.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{12}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
STALE_IDS = {
    "20261003-live-test-store-scope",
    "20261008-alembic-single-head-0136",
    "unknown",
    "dev",
}


def _sha_from_gitdir(git_dir: Path) -> str | None:
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(None, 1)[1].strip()
        ref_file = git_dir / ref
        if ref_file.is_file():
            token = ref_file.read_text(encoding="utf-8").strip().split()[0]
            if FULL_SHA_RE.fullmatch(token):
                return token[:12]
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == ref and FULL_SHA_RE.fullmatch(parts[0]):
                    return parts[0][:12]
        return None
    if FULL_SHA_RE.fullmatch(head):
        return head[:12]
    return None


def _first_line(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            return text
    return ""


def resolve_source_revision(stamp: str, dotgit: Path, compose_arg: str) -> str:
    if stamp in STALE_IDS or compose_arg in STALE_IDS:
        raise SystemExit("refusing stale source revision label")
    if compose_arg and compose_arg != "unknown" and stamp and compose_arg != stamp:
        raise SystemExit("RIBDIGI_SOURCE_REV does not match ribdigi-build-id.txt")
    sha = _sha_from_gitdir(dotgit) if dotgit.is_dir() else None
    chosen = sha or stamp
    if not SHA_RE.fullmatch(chosen or ""):
        raise SystemExit(f"build id must be a 12-character git sha, got {chosen!r}")
    if chosen in STALE_IDS:
        raise SystemExit("refusing stale source revision")
    return chosen


def main() -> None:
    stamp = _first_line(Path("/tmp/ribdigi-build-id.txt"))
    chosen = resolve_source_revision(
        stamp,
        Path("/tmp/dotgit"),
        (os.environ.get("RIBDIGI_SOURCE_REV") or "").strip(),
    )
    Path("/app/.build-id").write_text(chosen + "\n", encoding="utf-8")
    print(f"source revision {chosen}")


if __name__ == "__main__":
    main()
