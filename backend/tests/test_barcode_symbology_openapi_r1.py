"""Barcode symbology Query OpenAPI Literal (BR-5.1 / SYMBOLOGIES)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.barcodes import SYMBOLOGIES
from app.schemas import BarcodeSymbologyValue

ROOT = Path(__file__).resolve().parents[2]


def test_barcode_symbology_literal_covers_symbologies():
    lit = BarcodeSymbologyValue.__args__[0]
    assert set(lit.__args__) == set(SYMBOLOGIES)


def test_barcode_symbology_literal_schema():
    adapter = TypeAdapter(BarcodeSymbologyValue)
    assert adapter.validate_python("ean13") == "ean13"
    assert adapter.validate_python("  EAN13 ") == "ean13"
    assert adapter.validate_python("Code128") == "code128"
    assert adapter.validate_python("  UpCa ") == "upca"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("qr")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_barcode_symbology_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'value="code128"' in page
    assert 'value="ean13"' in page
    assert 'value="upca"' in page
    assert "Barcode symbology" in page or "barcodeSymbology" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Barcode symbology OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Barcode symbology" in docs
    assert "422" in docs
