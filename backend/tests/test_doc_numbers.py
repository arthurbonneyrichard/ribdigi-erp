from app.doc_numbers import format_daily_number, _max_seq


def test_format_daily_number_starts_at_001():
    assert format_daily_number("S", "260811", 1) == "S260811-001"
    assert format_daily_number("I", "260811", 12) == "I260811-012"


def test_max_seq_from_existing_refs():
    refs = ["S260811-001", "S260811-003", "S260810-009", "POS_SALE-old"]
    assert _max_seq(refs, "S260811-") == 3
    assert _max_seq([], "S260811-") == 0
