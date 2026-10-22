"""Write ops evidence without requiring /opt/ribdigi.

CI / operator machines may persist under /opt/ribdigi/artifacts. A laptop
without that tree still validates the payload by writing to a temp file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def write_ops_evidence(preferred: Path, text: str) -> Path:
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        preferred.write_text(text, encoding="utf-8")
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "ribdigi-ops-evidence" / preferred.name
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(text, encoding="utf-8")
        return fallback
