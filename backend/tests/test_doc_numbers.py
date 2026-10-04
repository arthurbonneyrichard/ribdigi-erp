from datetime import datetime

from app.doc_numbers import (
    format_daily_number,
    format_series_number,
    _max_seq,
    invoice_numbering_settings,
)


def test_format_daily_number_starts_at_001():
    assert format_daily_number("S", "260811", 1) == "S260811-001"
    assert format_daily_number("I", "260811", 12) == "I260811-012"


def test_format_series_number():
    assert format_series_number("INV", 2026, 1) == "INV-2026-0001"
    assert format_series_number("SI", 2026, 42) == "SI-2026-0042"


def test_invoice_numbering_settings_preview_resets_on_year_change():
    class T:
        sales_invoice_number_prefix = "INV"
        sales_invoice_number_next = 9
        sales_invoice_number_year = 2025

    cfg = invoice_numbering_settings(T(), as_of=datetime(2026, 3, 1))
    assert cfg["next_number"] == 1
    assert cfg["preview"] == "INV-2026-0001"
    assert cfg["year"] == 2026


def test_max_seq_from_existing_refs():
    refs = ["S260811-001", "S260811-003", "S260810-009", "POS_SALE-old"]
    assert _max_seq(refs, "S260811-") == 3
    assert _max_seq([], "S260811-") == 0
