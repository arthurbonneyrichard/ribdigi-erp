from app.tax import compute_line_total, compute_tax_amounts


def test_exclusive_tax():
    net, tax, gross = compute_tax_amounts(100, 15, "exclusive")
    assert net == 100
    assert tax == 15
    assert gross == 115


def test_inclusive_tax():
    net, tax, gross = compute_tax_amounts(115, 15, "inclusive")
    assert gross == 115
    assert tax == 15
    assert net == 100


def test_line_total_delegates():
    subtotal, tax, total = compute_line_total(2, 50, 10)
    assert subtotal == 100
    assert tax == 10
    assert total == 110


def test_zero_rate():
    net, tax, gross = compute_tax_amounts(80, 0)
    assert net == 80 and tax == 0 and gross == 80
