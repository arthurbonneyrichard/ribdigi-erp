from datetime import datetime

import pytest
from fastapi import HTTPException

from app.doc_numbers import (
    apply_numbering_update,
    format_daily_number,
    format_series_number,
    _max_seq,
    invoice_numbering_settings,
    numbering_settings,
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


def test_pos_and_shift_prefixes_are_server_locked():
    class T:
        document_numbering = {
            "pos_sale": {"prefix": "HACK", "next": 9, "year": 2026},
            "pos_session": {"prefix": "X", "next": 3, "year": 2026},
        }
        sales_invoice_number_prefix = "INV"
        sales_invoice_number_next = 1
        sales_invoice_number_year = 2026

    sale = numbering_settings(T(), "pos_sale", as_of=datetime(2026, 6, 1))
    assert sale["prefix"] == "POS"
    assert sale["preview"] == "POS-2026-0009"
    assert sale["server_allocated"] is True
    assert sale["editable"] is False

    shift = numbering_settings(T(), "pos_session", as_of=datetime(2026, 6, 1))
    assert shift["prefix"] == "SHIFT"
    assert shift["preview"] == "SHIFT-2026-0003"
    assert shift["server_allocated"] is True


def test_apply_numbering_update_rejects_pos_and_shift():
    class T:
        document_numbering = {}
        sales_invoice_number_prefix = "INV"
        sales_invoice_number_next = 1
        sales_invoice_number_year = 2026

    with pytest.raises(HTTPException) as exc:
        apply_numbering_update(T(), "pos_sale", prefix="POS", next_number=1)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        apply_numbering_update(T(), "pos_session", prefix="SHIFT", next_number=1)
    assert exc.value.status_code == 400
