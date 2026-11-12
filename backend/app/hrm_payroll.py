"""Payroll arithmetic for the HRM desk, in Decimal throughout.

No database here: `compute_payslip` takes one person's month and the statutory rates
in force, and returns every figure on the payslip. Rates are data (an effective-dated
`hrm_statutory_rates` row, or the company's older `hrm_settings`), never constants in
this file, so a change in GRA bands or SSNIT rules is an admin entry, not a code change.

Ghana shape it follows (values come from the rate row):
- SSNIT is taken on basic salary actually earned, optionally capped at the maximum
  insurable earnings. Staff pay `employee_percent`, the company `employer_percent`.
- The combined contribution splits into Tier 1 (to SSNIT) and Tier 2 (to the
  company's occupational pension trustee) by `tier2_percent` of insurable earnings.
  A rate row with tier2_percent 0 sends it all to SSNIT, as the desk always did.
- Tier 3 is voluntary, a percent of earned basic set per person. It is relieved
  from tax up to `tier3_relief_percent` of earned basic.
- PAYE is charged band by band on gross less staff SSNIT less relieved Tier 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")
ROUNDING_MODES = {"half_up": ROUND_HALF_UP, "down": ROUND_DOWN}


def D(value) -> Decimal:
    """Money in: never through float arithmetic. Floats are read by their printed value."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class StatutoryRates:
    employee_percent: Decimal
    employer_percent: Decimal
    paye_bands: list[dict]
    tier2_percent: Decimal = ZERO
    insurable_cap: Decimal | None = None
    tier3_relief_percent: Decimal = Decimal("16.5")
    rounding: str = "half_up"
    rate_id: str | None = None
    effective_from: str | None = None

    def snapshot(self) -> dict:
        """What a payslip keeps, so the figures can be explained after the rates change."""
        return {
            "rate_id": self.rate_id,
            "effective_from": self.effective_from,
            "employee_percent": str(self.employee_percent),
            "employer_percent": str(self.employer_percent),
            "tier2_percent": str(self.tier2_percent),
            "insurable_cap": str(self.insurable_cap) if self.insurable_cap is not None else None,
            "tier3_relief_percent": str(self.tier3_relief_percent),
            "rounding": self.rounding,
            "paye_bands": [
                {"width": (str(b["width"]) if b.get("width") is not None else None), "rate": str(b.get("rate") or 0)}
                for b in self.paye_bands
            ],
        }


@dataclass
class PayslipInput:
    basic: Decimal
    allowances: Decimal = ZERO
    bonus: Decimal = ZERO
    other_deductions: Decimal = ZERO
    unpaid_days: int = 0
    working_days: int = 22
    tier3_percent: Decimal = ZERO


@dataclass
class PayslipResult:
    unpaid_deduction: Decimal
    earned_basic: Decimal
    gross: Decimal
    insurable: Decimal
    ssnit_employee: Decimal
    ssnit_employer: Decimal
    tier1: Decimal
    tier2: Decimal
    tier3: Decimal
    tier3_relief: Decimal
    taxable: Decimal
    paye: Decimal
    net: Decimal
    paye_by_band: list[dict] = field(default_factory=list)


class PayrollError(ValueError):
    """A payslip that cannot be paid as entered (deductions above pay, bad bands)."""


def _round(value: Decimal, rates: StatutoryRates) -> Decimal:
    mode = ROUNDING_MODES.get(rates.rounding, ROUND_HALF_UP)
    return value.quantize(CENT, rounding=mode)


def validate_bands(bands: list[dict]) -> None:
    if not bands:
        raise PayrollError("Add at least one PAYE band")
    if bands[-1].get("width") is not None or any(b.get("width") is None for b in bands[:-1]):
        raise PayrollError("Only the last PAYE band can be open-ended, and it must be")
    for band in bands:
        rate = D(band.get("rate"))
        if rate < 0 or rate > HUNDRED:
            raise PayrollError("A PAYE rate must be between 0 and 100")
        if band.get("width") is not None and D(band["width"]) <= 0:
            raise PayrollError("A PAYE band must be wider than zero")


def paye(taxable: Decimal, rates: StatutoryRates) -> tuple[Decimal, list[dict]]:
    """Tax on a month's taxable pay, band by band. Rounded once, on the total."""
    left = max(D(taxable), ZERO)
    tax = ZERO
    rows: list[dict] = []
    for band in rates.paye_bands:
        width = band.get("width")
        chunk = left if width is None else min(left, D(width))
        rate = D(band.get("rate"))
        part = chunk * rate / HUNDRED
        rows.append({"chunk": chunk, "rate": rate, "tax": part})
        tax += part
        left -= chunk
        if left <= 0:
            break
    return _round(tax, rates), rows


def compute_payslip(item: PayslipInput, rates: StatutoryRates) -> PayslipResult:
    basic = D(item.basic)
    days = max(int(item.working_days or 0), 1)
    per_day = basic / Decimal(days)
    unpaid = min(_round(per_day * Decimal(int(item.unpaid_days or 0)), rates), basic)
    earned = basic - unpaid
    gross = earned + D(item.allowances) + D(item.bonus)

    insurable = earned
    if rates.insurable_cap is not None and rates.insurable_cap >= 0:
        insurable = min(earned, rates.insurable_cap)
    ssnit_employee = _round(insurable * rates.employee_percent / HUNDRED, rates)
    ssnit_employer = _round(insurable * rates.employer_percent / HUNDRED, rates)
    combined = ssnit_employee + ssnit_employer
    tier2 = _round(insurable * rates.tier2_percent / HUNDRED, rates) if rates.tier2_percent > 0 else ZERO
    tier2 = min(tier2, combined)
    tier1 = combined - tier2

    tier3 = _round(earned * D(item.tier3_percent) / HUNDRED, rates) if D(item.tier3_percent) > 0 else ZERO
    relief_cap = _round(earned * rates.tier3_relief_percent / HUNDRED, rates)
    tier3_relief = min(tier3, relief_cap)

    taxable = gross - ssnit_employee - tier3_relief
    if taxable < 0:
        taxable = ZERO
    tax, by_band = paye(taxable, rates)
    net = gross - ssnit_employee - tier3 - tax - D(item.other_deductions)
    if net < 0:
        raise PayrollError("Deductions are more than this person's pay")
    return PayslipResult(
        unpaid_deduction=unpaid,
        earned_basic=earned,
        gross=gross,
        insurable=insurable,
        ssnit_employee=ssnit_employee,
        ssnit_employer=ssnit_employer,
        tier1=tier1,
        tier2=tier2,
        tier3=tier3,
        tier3_relief=tier3_relief,
        taxable=taxable,
        paye=tax,
        net=net,
        paye_by_band=by_band,
    )
