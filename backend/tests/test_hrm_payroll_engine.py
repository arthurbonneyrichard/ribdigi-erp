"""Payroll arithmetic, checked against figures worked out by hand.

The bands below are the monthly PAYE bands the desk ships with (GRA 2024 monthly
table). They are test inputs here; the live values are whatever the company enters.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.hrm_payroll import PayrollError, PayslipInput, StatutoryRates, compute_payslip, validate_bands

BANDS = [
    {"width": "490", "rate": "0"},
    {"width": "110", "rate": "5"},
    {"width": "130", "rate": "10"},
    {"width": "3166.67", "rate": "17.5"},
    {"width": "16000", "rate": "25"},
    {"width": "30520", "rate": "30"},
    {"width": None, "rate": "35"},
]


def rates(**extra) -> StatutoryRates:
    base = {"employee_percent": Decimal("5.5"), "employer_percent": Decimal("13"), "paye_bands": BANDS}
    base.update(extra)
    return StatutoryRates(**base)


def test_plain_month_matches_hand_figures():
    # Basic 5,000 + allowance 1,000. SSNIT 5.5% of 5,000 = 275. Taxable 5,725.
    # PAYE 0 + 5.50 + 13.00 + 554.16725 + 25% of 1,828.33 (457.0825) = 1,029.74975 -> 1,029.75.
    out = compute_payslip(PayslipInput(basic=Decimal("5000"), allowances=Decimal("1000")), rates())
    assert out.gross == Decimal("6000")
    assert out.ssnit_employee == Decimal("275.00")
    assert out.ssnit_employer == Decimal("650.00")
    assert out.taxable == Decimal("5725.00")
    assert out.paye == Decimal("1029.75")
    assert out.net == Decimal("4695.25")
    # No Tier 2 configured: the whole 925 goes to SSNIT, as the desk always did.
    assert out.tier1 == Decimal("925.00") and out.tier2 == Decimal("0")


def test_unpaid_days_come_off_basic_before_ssnit_and_tax():
    # 2,200 over 22 days is 100 a day; 2 unpaid days take 200, so 2,000 is earned.
    # SSNIT 110. Taxable 1,890: 5.50 + 13.00 + 17.5% of 1,160 (203.00) = 221.50.
    out = compute_payslip(PayslipInput(basic=Decimal("2200"), unpaid_days=2, working_days=22), rates())
    assert out.unpaid_deduction == Decimal("200.00")
    assert out.ssnit_employee == Decimal("110.00")
    assert out.paye == Decimal("221.50")
    assert out.net == Decimal("1668.50")


def test_tiers_cap_and_voluntary_relief():
    # Cap 10,000 on insurable pay. Staff 550, company 1,300, together 1,850.
    # Tier 2 is 5% of 10,000 = 500; Tier 1 the other 1,350.
    # Tier 3 voluntary 3% of 12,000 = 360, inside the 16.5% relief (1,980), so all relieved.
    # Taxable 12,000 - 550 - 360 = 11,090.
    # PAYE 5.50 + 13.00 + 554.16725 + 25% of 7,193.33 (1,798.3325) = 2,370.99975 -> 2,371.00.
    out = compute_payslip(
        PayslipInput(basic=Decimal("12000"), tier3_percent=Decimal("3")),
        rates(tier2_percent=Decimal("5"), insurable_cap=Decimal("10000")),
    )
    assert out.insurable == Decimal("10000")
    assert (out.ssnit_employee, out.ssnit_employer) == (Decimal("550.00"), Decimal("1300.00"))
    assert (out.tier1, out.tier2) == (Decimal("1350.00"), Decimal("500.00"))
    assert (out.tier3, out.tier3_relief) == (Decimal("360.00"), Decimal("360.00"))
    assert out.taxable == Decimal("11090.00")
    assert out.paye == Decimal("2371.00")
    assert out.net == Decimal("8719.00")


def test_tier3_above_relief_is_taxed():
    # 20% voluntary on 1,000 = 200, but only 16.5% (165) is relieved.
    out = compute_payslip(PayslipInput(basic=Decimal("1000"), tier3_percent=Decimal("20")), rates())
    assert out.tier3 == Decimal("200.00")
    assert out.tier3_relief == Decimal("165.00")
    assert out.taxable == Decimal("780.00")  # 1,000 - 55 SSNIT - 165 relief


def test_rounding_rule_is_configurable():
    up = compute_payslip(PayslipInput(basic=Decimal("5000"), allowances=Decimal("1000")), rates())
    down = compute_payslip(PayslipInput(basic=Decimal("5000"), allowances=Decimal("1000")), rates(rounding="down"))
    assert up.paye == Decimal("1029.75")
    assert down.paye == Decimal("1029.74")


def test_no_float_drift():
    # 0.1 + 0.2 style sums stay exact.
    out = compute_payslip(PayslipInput(basic=Decimal("0.30"), allowances=Decimal("0.10")), rates(employee_percent=Decimal("0")))
    assert out.gross == Decimal("0.40")


def test_deductions_above_pay_are_refused():
    with pytest.raises(PayrollError):
        compute_payslip(PayslipInput(basic=Decimal("500"), other_deductions=Decimal("600")), rates())


def test_bands_must_end_open():
    with pytest.raises(PayrollError):
        validate_bands([{"width": "100", "rate": "0"}])
    with pytest.raises(PayrollError):
        validate_bands([{"width": None, "rate": "0"}, {"width": None, "rate": "5"}])
    validate_bands(BANDS)


def test_arrears_attract_ssnit_and_corrections_do_not():
    # 1,000 basic + 200 back pay of basic: SSNIT on 1,200 (66). Correction +100 is taxable, no SSNIT.
    out = compute_payslip(
        PayslipInput(basic=Decimal("1000"), arrears_basic=Decimal("200"), adjustment=Decimal("100")), rates()
    )
    assert out.ssnit_employee == Decimal("66.00")
    assert out.gross == Decimal("1300")
    assert out.taxable == Decimal("1234.00")
    with pytest.raises(PayrollError):
        compute_payslip(PayslipInput(basic=Decimal("100"), adjustment=Decimal("-500")), rates())


def test_junior_overtime_is_taxed_on_its_own():
    # Basic 1,200 (under a 1,500 cap), overtime 800. Low part = 50% of 1,200 = 600 at 5% = 30;
    # the other 200 at 10% = 20. Overtime tax 50, outside the PAYE bands.
    junior = rates(overtime_junior_cap=Decimal("1500"))
    out = compute_payslip(PayslipInput(basic=Decimal("1200"), overtime=Decimal("800")), junior)
    assert out.overtime_tax == Decimal("50.00")
    assert out.taxable == Decimal("1134.00")  # 1,200 - 66 SSNIT; overtime left out
    plain = compute_payslip(PayslipInput(basic=Decimal("1200")), junior)
    assert out.paye == plain.paye + Decimal("50.00")
    assert out.gross == Decimal("2000")


def test_overtime_is_ordinary_pay_without_the_rule_or_above_the_cap():
    off = compute_payslip(PayslipInput(basic=Decimal("1200"), overtime=Decimal("800")), rates())
    assert off.overtime_tax == 0 and off.taxable == Decimal("1934.00")
    senior = compute_payslip(PayslipInput(basic=Decimal("3000"), overtime=Decimal("800")), rates(overtime_junior_cap=Decimal("1500")))
    assert senior.overtime_tax == 0 and senior.taxable == Decimal("3635.00")


def test_minimum_wage_flag():
    floor = rates(minimum_daily_wage=Decimal("20"))
    assert compute_payslip(PayslipInput(basic=Decimal("400"), working_days=22), floor).warnings == ["below_minimum_wage"]
    assert compute_payslip(PayslipInput(basic=Decimal("440"), working_days=22), floor).warnings == []
    assert compute_payslip(PayslipInput(basic=Decimal("400")), rates()).warnings == []
