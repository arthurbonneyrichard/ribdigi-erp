"""Shrink pictures uploaded before uploads were optimised (product, brand, banner, receipt images).

    cd backend && PYTHONPATH=. python scripts/optimize_existing_images.py          # report only
    cd backend && PYTHONPATH=. python scripts/optimize_existing_images.py --apply  # rewrite files

Keys do not change, so nothing that points at a picture breaks. The company logo is left alone
(printing and PDFs use its original). Take a backup of the media folder or bucket first.
"""

from __future__ import annotations

import sys

from app import storage


def main() -> None:
    apply = "--apply" in sys.argv
    report = storage.optimize_existing(dry_run=not apply)
    saved = report["bytes_before"] - report["bytes_after"]
    print(
        f"{'Rewrote' if apply else 'Would shrink'} {report['shrunk']} of {report['checked']} pictures, "
        f"saving {saved / 1_000_000:.1f} MB"
    )
    if not apply:
        print("Run again with --apply to do it.")


if __name__ == "__main__":
    main()
