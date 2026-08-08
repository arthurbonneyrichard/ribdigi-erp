from app.accounting import lines_are_balanced


def test_balanced_journal_lines():
    assert lines_are_balanced(
        [
            {"debit": 100, "credit": 0},
            {"debit": 0, "credit": 100},
        ]
    )


def test_unbalanced_journal_lines_rejected():
    assert not lines_are_balanced(
        [
            {"debit": 100, "credit": 0},
            {"debit": 0, "credit": 99},
        ]
    )


def test_balance_tolerance():
    assert lines_are_balanced(
        [
            {"debit": 100.004, "credit": 0},
            {"debit": 0, "credit": 100},
        ]
    )
