from app.pos import compute_expected_cash, compute_variance, normalize_payment_method


def test_expected_cash():
    assert compute_expected_cash(200, 150.5) == 350.5


def test_variance():
    assert compute_variance(845, 850.5) == -5.5


def test_normalize_payment_method():
    assert normalize_payment_method("CASH") == "cash"
    assert normalize_payment_method("Card") == "card"
    assert normalize_payment_method("unknown") == "other"
