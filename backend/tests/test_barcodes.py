from fastapi import HTTPException
import pytest

from app.barcodes import (
    detect_symbology,
    ean13_check_digit,
    looks_like_barcode,
    normalize_barcode,
    render_barcode_png,
    render_code128_png,
    suggest_barcode,
    suggest_barcode_from_sku,
    upca_check_digit,
    validate_ean13,
    validate_upca,
)


def test_looks_like_barcode():
    assert looks_like_barcode("WATER-500")
    assert looks_like_barcode("8901234567890")
    assert not looks_like_barcode("bag of rice")
    assert not looks_like_barcode("ab")


def test_suggest_and_render_code128():
    code = suggest_barcode_from_sku("rice 5kg!")
    assert code == "RICE5KG"
    png = render_code128_png(code)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_normalize_barcode():
    assert normalize_barcode("  water-500 ") == "WATER-500"
    assert normalize_barcode("") is None


def test_ean13_check_and_validate():
    body = "200123456789"
    check = ean13_check_digit(body)
    code = body + check
    assert validate_ean13(code) == code
    with pytest.raises(HTTPException) as exc:
        validate_ean13(body + ("0" if check != "0" else "1"))
    assert exc.value.status_code == 400


def test_upca_check_and_validate():
    body = "21234567890"
    check = upca_check_digit(body)
    code = body + check
    assert validate_upca(code) == code
    with pytest.raises(HTTPException):
        validate_upca(body + ("0" if check != "0" else "1"))


def test_suggest_and_render_ean13_upca():
    ean = suggest_barcode("WIDGET", symbology="ean13", seed="p1", attempt=0)
    assert len(ean) == 13 and ean.isdigit()
    assert ean.startswith("200")
    assert detect_symbology(ean) == "ean13"
    png_e = render_barcode_png(ean, symbology="ean13")
    assert png_e[:8] == b"\x89PNG\r\n\x1a\n"

    upc = suggest_barcode("WIDGET", symbology="upca", seed="p1", attempt=0)
    assert len(upc) == 12 and upc.isdigit()
    assert upc.startswith("2")
    assert detect_symbology(upc) == "upca"
    png_u = render_barcode_png(upc, symbology="upca")
    assert png_u[:8] == b"\x89PNG\r\n\x1a\n"


def test_normalize_auto_gtin():
    ean = suggest_barcode("X", symbology="ean13", seed="auto", attempt=0)
    assert normalize_barcode(ean) == ean
    with pytest.raises(HTTPException):
        normalize_barcode("1234567890123")  # bad check digit
