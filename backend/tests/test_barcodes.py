from app.barcodes import looks_like_barcode, normalize_barcode, render_code128_png, suggest_barcode_from_sku


def test_looks_like_barcode():
    assert looks_like_barcode("WATER-500")
    assert looks_like_barcode("8901234567890")
    assert not looks_like_barcode("bag of rice")
    assert not looks_like_barcode("ab")


def test_suggest_and_render():
    code = suggest_barcode_from_sku("rice 5kg!")
    assert code == "RICE5KG"
    png = render_code128_png(code)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_normalize_barcode():
    assert normalize_barcode("  water-500 ") == "WATER-500"
    assert normalize_barcode("") is None
