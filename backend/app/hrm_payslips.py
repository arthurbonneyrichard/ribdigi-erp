"""HRM payslips on paper and by email, and the salary payment file for the bank or Mobile Money.

A payslip only leaves the system once its payroll is approved. The email body carries no pay
figures (mailboxes are shared and forwarded); the figures are in the attached PDF.
"""

from __future__ import annotations

import csv
import html
import io
import logging
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import emailer
from app import hrm as svc
from app import models as m
from app import hrm_payroll as engine

logger = logging.getLogger(__name__)

PaymentMethod = Literal["bank", "mobile_money"]


def _n(value) -> float:
    return float(engine.D(value or 0))


def slip_lines(slip: dict) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """Earnings and deductions as shown on the payslip (zero lines left out, except basic)."""
    earn = [("Basic salary", _n(slip["basic"]))]
    for label, key in (
        ("Allowances", "allowances"), ("Bonus", "bonus"), ("Back pay of basic", "arrears_basic"),
        ("Correction", "adjustment"), ("Overtime", "overtime"), ("Commission", "commission"),
        ("Tips", "tips"), ("Unused leave paid", "leave_pay"),
    ):
        if _n(slip.get(key)):
            earn.append((label, _n(slip.get(key))))
    if _n(slip.get("unpaid_deduction")):
        days = int(slip.get("unpaid_days") or 0)
        earn.append((f"Unpaid days ({days})" if days else "Unpaid days", -_n(slip["unpaid_deduction"])))
    ded: list[tuple[str, float]] = []
    if _n(slip.get("ssnit_employee")):
        ded.append(("SSNIT (5.5%)", _n(slip["ssnit_employee"])))
    if _n(slip.get("tier3")):
        ded.append(("Tier 3 pension", _n(slip["tier3"])))
    ded.append(("PAYE income tax", _n(slip.get("paye"))))
    part = _n(slip.get("part_paid"))
    loan = _n(slip.get("loan_deduction")) - part
    if part > 0:
        ded.append(("Paid during the month", part))
    if loan > 0:
        ded.append(("Loan / advance repayment", loan))
    if _n(slip.get("other_deductions")):
        ded.append(("Other deductions", _n(slip["other_deductions"])))
    return earn, ded


async def _slip_with_run(db: AsyncSession, tenant_id: str, slip_id: str):
    row = (
        await db.execute(
            select(m.HrmPayslip, m.HrmPayrollRun)
            .join(m.HrmPayrollRun, m.HrmPayrollRun.id == m.HrmPayslip.run_id)
            .where(m.HrmPayslip.tenant_id == tenant_id, m.HrmPayslip.id == slip_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Payslip not found")
    return row


def _mask(value: str | None) -> str:
    text = (value or "").strip()
    return ("****" + text[-4:]) if len(text) > 4 else text


def payslip_pdf(tenant: m.Tenant | None, slip: m.HrmPayslip, run: m.HrmPayrollRun, person: m.HrmEmployee) -> bytes:
    from app.document_print import letterhead_payload, to_document_a4_pdf

    data = svc._slip_dict(slip, person)
    currency = (getattr(tenant, "currency", None) or "GHS").upper()
    money = lambda v: f"{currency} {v:,.2f}"  # noqa: E731
    earn, ded = slip_lines(data)
    totals: list[tuple[str, str, bool]] = [(label, money(v), False) for label, v in earn]
    totals.append(("Gross pay", money(_n(data["gross"])), True))
    totals += [(label, money(-v), False) for label, v in ded]
    totals.append(("Net pay", money(_n(data["net"])), True))
    notes = []
    if _n(data.get("overtime_tax")):
        notes.append(f"PAYE includes overtime tax of {money(_n(data['overtime_tax']))}.")
    if _n(data.get("bonus_tax")):
        notes.append(f"PAYE includes the final bonus tax of {money(_n(data['bonus_tax']))}.")
    if data.get("non_resident"):
        notes.append("Taxed as a non-resident.")
    if data.get("ssnit_exempt"):
        notes.append("Not in SSNIT: no SSNIT deducted.")
    notes.append(f"Company SSNIT on your behalf: {money(_n(data.get('ssnit_employer')))}.")
    payload = {
        **letterhead_payload(tenant, currency=currency),
        "title": "Payslip",
        "doc_heading": f"PAYSLIP {run.period}",
        "table": "none",
        "items": [],
        "party_label": "Employee",
        "party_name": person.full_name,
        "party_detail": " · ".join(x for x in (person.employee_number, person.job_title, person.department) if x),
        "meta_left": [
            f"Pay month: {run.period}",
            f"Payroll: {run.run_number}" if getattr(run, "run_number", None) else "",
        ],
        "meta_right": [
            f"SSNIT no: {person.ssnit_number or '-'}",
            f"TIN: {person.tin or person.ghana_card or '-'}",
            f"Paid to: {_mask(person.bank_account) or _mask(person.mobile_money) or '-'}",
        ],
        "totals": totals,
        "notes": " ".join(notes),
    }
    return to_document_a4_pdf(payload)


async def pdf_for(db: AsyncSession, tenant_id: str, slip_id: str, claims: dict) -> tuple[bytes, str]:
    """HR with payroll rights get any payslip; anyone else only their own, once approved."""
    slip, run = await _slip_with_run(db, tenant_id, slip_id)
    try:
        svc.job(claims, "payroll")
        is_hr = True
    except HTTPException:
        is_hr = False
    person = await db.get(m.HrmEmployee, slip.employee_id)
    if not is_hr:
        me = await svc.employee_for_user(db, tenant_id, claims.get("sub"))
        if not me or me.id != slip.employee_id or run.status == "draft":
            raise HTTPException(status_code=404, detail="Payslip not found")
    tenant = await db.get(m.Tenant, tenant_id)
    filename = f"payslip_{run.period}_{(person.employee_number or person.id)}.pdf".replace(" ", "_")
    return payslip_pdf(tenant, slip, run, person), filename


async def email_run(db: AsyncSession, tenant_id: str, run_id: str, *, resend: bool, user_id) -> dict:
    run = await svc._run(db, tenant_id, run_id)
    if run.status == "draft":
        raise HTTPException(status_code=409, detail="Approve the payroll before sending payslips")
    tenant = await db.get(m.Tenant, tenant_id)
    company = (getattr(tenant, "company_name", None) or "Your employer").strip()
    slips = (await db.execute(select(m.HrmPayslip).where(m.HrmPayslip.run_id == run.id))).scalars().all()
    sent, failed, no_email, skipped = [], [], [], 0
    for slip in slips:
        person = await db.get(m.HrmEmployee, slip.employee_id)
        if slip.emailed_at and not resend:
            skipped += 1
            continue
        to = (person.email or "").strip()
        if not to:
            no_email.append(person.full_name)
            continue
        pdf = payslip_pdf(tenant, slip, run, person)
        text = (
            f"Dear {person.full_name},\n\nYour payslip for {run.period} from {company} is attached.\n\n"
            "Keep it private. If anything on it looks wrong, speak to HR."
        )
        inner = (
            f"<p>Dear {html.escape(person.full_name)},</p>"
            f"<p>Your payslip for <strong>{html.escape(run.period)}</strong> from {html.escape(company)} is attached.</p>"
            "<p>Keep it private. If anything on it looks wrong, speak to HR.</p>"
        )
        result = await emailer.send_email(
            to=to,
            subject=f"Your payslip for {run.period}",
            text_body=text,
            html_body=emailer.render_branded_html(body_html=inner, company_name=company, tenant=tenant, title="Your payslip"),
            attachments=[{
                "filename": f"payslip_{run.period}.pdf",
                "content": pdf,
                "content_type": "application/pdf",
            }],
            tenant=tenant,
        )
        if result.mode == "disabled":
            raise HTTPException(status_code=503, detail="Email delivery is turned off. Set up company email first.")
        if result.sent:
            slip.emailed_at = datetime.utcnow()
            sent.append(person.full_name)
        else:
            failed.append(person.full_name)
    await svc._audit(
        db, tenant_id, user_id, "hrm_payslips_emailed", "hrm_payroll_run", run.id,
        {"period": run.period, "sent": len(sent), "failed": len(failed), "no_email": len(no_email), "skipped": skipped},
    )
    return {"sent": len(sent), "failed": failed, "no_email": no_email, "already_sent": skipped}


def _cell(value) -> str:
    """Spreadsheet-safe text: a leading = + - @ is not run as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


async def payment_file(db: AsyncSession, tenant_id: str, run_id: str, method: PaymentMethod, *, user_id) -> tuple[str, dict]:
    """CSV of net pay for the bank's bulk upload or a Mobile Money bulk payment. Staff paid the
    other way, or with no account number, are listed as left out."""
    run = await svc._run(db, tenant_id, run_id)
    if run.status == "draft":
        raise HTTPException(status_code=409, detail="Approve the payroll before making the payment file")
    rows = (
        await db.execute(
            select(m.HrmPayslip, m.HrmEmployee)
            .join(m.HrmEmployee, m.HrmEmployee.id == m.HrmPayslip.employee_id)
            .where(m.HrmPayslip.run_id == run.id)
            .order_by(m.HrmEmployee.full_name)
        )
    ).all()
    out = io.StringIO()
    w = csv.writer(out)
    if method == "bank":
        w.writerow(["Employee number", "Name", "Bank", "Account number", "Amount", "Reference"])
    else:
        w.writerow(["Employee number", "Name", "Mobile Money number", "Amount", "Reference"])
    total = engine.ZERO
    count = 0
    left_out = []
    reference = f"Salary {run.period}"
    for slip, person in rows:
        net = engine.D(slip.net)
        if net <= 0:
            continue
        account = (person.bank_account if method == "bank" else person.mobile_money) or ""
        if not account.strip():
            left_out.append(person.full_name)
            continue
        if method == "bank":
            w.writerow([_cell(person.employee_number), _cell(person.full_name), _cell(person.bank_name), _cell(account.strip()), f"{net:.2f}", reference])
        else:
            w.writerow([_cell(person.employee_number), _cell(person.full_name), _cell(account.strip()), f"{net:.2f}", reference])
        total += net
        count += 1
    await svc._audit(
        db, tenant_id, user_id, "hrm_payment_file_made", "hrm_payroll_run", run.id,
        {"period": run.period, "method": method, "count": count, "left_out": len(left_out)},
    )
    return out.getvalue(), {"count": count, "total": float(total), "left_out": left_out}
