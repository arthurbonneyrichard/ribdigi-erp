"""HR assistant: plain-language questions answered from the HR records, by rules (no AI model).

It recognises common questions and answers each from the same functions the HR screens use,
so the answer always matches the screen. Who may ask what follows hrm.job: everyone can ask
about their own leave, payslips, documents, claims and manager; HR questions about other
people need the matching HR area. Pay amounts are never put in an answer; it points to the
payslip instead. Questions are logged like AI chat (hashed, redacted preview).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

# (intent, needs HR area or None for self, words that point to it)
INTENTS: list[tuple[str, str | None, tuple[str, ...]]] = [
    ("who_on_leave", "leave", ("who is on leave", "who's on leave", "who is off", "on leave today", "away today")),
    ("pending_leave", "leave", ("leave waiting", "pending leave", "leave to decide", "leave requests waiting")),
    ("headcount", "people", ("headcount", "how many staff", "how many people work", "how many employees", "staff count")),
    ("contracts", "contracts", ("contract", "probation")),
    ("signals", "people", ("signal", "worry", "concern", "who needs attention", "absence pattern")),
    ("payroll_state", "payroll", ("payroll", "pay run", "this month's pay")),
    ("my_manager", None, ("my manager", "who approves", "report to", "my boss")),
    ("my_leave", None, ("my leave", "leave do i have", "leave days", "days left", "leave balance", "annual leave")),
    ("my_payslip", None, ("payslip", "pay slip", "my pay", "salary", "when am i paid")),
    ("my_documents", None, ("document", "policy", "handbook", "accept")),
    ("my_claims", None, ("claim", "refund", "money i spent")),
]

HELP = (
    "I can answer: how much leave you have, your payslips, your manager, documents to accept and your claims. "
    "HR can also ask who is on leave today, leave waiting, headcount, contracts ending, people signals and payroll."
)


def match(question: str) -> str | None:
    text = re.sub(r"\s+", " ", question.lower())
    for intent, _area, words in INTENTS:
        if any(w in text for w in words):
            return intent
    return None


def _area(intent: str) -> str | None:
    return next(a for i, a, _w in INTENTS if i == intent)


async def _me(db, tenant_id, user_id):
    from app import hrm

    try:
        return await hrm.employee_for_user(db, tenant_id, user_id)
    except HTTPException:
        return None


async def answer(db: AsyncSession, claims: dict, question: str) -> dict[str, Any]:
    from app import hrm

    tenant_id, user_id = claims["tenant_id"], claims.get("sub")
    intent = match(question)
    if intent is None:
        return {"intent": None, "answer": "I did not understand that. " + HELP, "link": None}
    area = _area(intent)
    if area:
        try:
            hrm.job(claims, area)
        except HTTPException:
            return {"intent": intent, "answer": "That is for HR. You can ask about your own leave, payslips, manager, documents and claims.", "link": None}
    else:
        me = await _me(db, tenant_id, user_id)
        if me is None:
            return {"intent": intent, "answer": "No staff record uses your login email, so I cannot find your file. Ask HR to add it.", "link": None}
    fn = globals()[f"_a_{intent}"]
    return {"intent": intent, **(await fn(db, tenant_id, user_id))}


async def _a_my_leave(db, tenant_id, user_id):
    from app import hrm

    me = await _me(db, tenant_id, user_id)
    bal = await hrm.leave_balance(db, tenant_id, me.id)
    pending = (
        await db.execute(
            select(func.count()).select_from(m.HrmLeaveRequest).where(
                m.HrmLeaveRequest.employee_id == me.id, m.HrmLeaveRequest.status == "pending"
            )
        )
    ).scalar_one()
    extra = f" {pending} request(s) are waiting for a decision." if pending else ""
    return {
        "answer": f"You have {bal['left']} annual leave day(s) left for {bal['year']} (of {bal['entitled']}; {bal['used']} used).{extra}",
        "link": "/hrm?tab=me",
    }


async def _a_my_payslip(db, tenant_id, user_id):
    from app import hrm

    me = await _me(db, tenant_id, user_id)
    slips = await hrm.my_slips(db, tenant_id, me)
    if not slips:
        return {"answer": "There is no approved payslip for you yet. It appears under My HR once the month's payroll is approved.", "link": "/hrm?tab=me"}
    return {"answer": f"Your latest payslip is for {slips[0].get('period')}. Open My HR to see or print it.", "link": "/hrm?tab=me"}


async def _a_my_manager(db, tenant_id, user_id):
    from app import hrm_delegation

    me = await _me(db, tenant_id, user_id)
    if not me.manager_id:
        return {"answer": "Nobody is set as your manager, so HR decides your leave.", "link": "/hrm?tab=me"}
    boss = await db.get(m.HrmEmployee, me.manager_id)
    cover = await hrm_delegation.active_for(db, me.manager_id)
    words = f"You report to {boss.full_name if boss else 'your manager'}; they decide your leave first, then HR."
    if cover is not None:
        deputy = await db.get(m.HrmEmployee, cover.to_employee_id)
        words += f" {deputy.full_name if deputy else 'A colleague'} covers for them until {cover.ends_on.isoformat()}."
    return {"answer": words, "link": "/hrm?tab=me"}


async def _a_my_documents(db, tenant_id, user_id):
    from app import hrm_documents

    me = await _me(db, tenant_id, user_id)
    docs = await hrm_documents.mine(db, tenant_id, me)
    waiting = [d["title"] for d in docs if d["needs_ack"] and not d.get("accepted_at")]
    if waiting:
        return {"answer": "To read and accept: " + ", ".join(waiting) + ".", "link": "/hrm?tab=me"}
    return {"answer": f"Nothing to accept. You have {len(docs)} document(s) under My HR.", "link": "/hrm?tab=me"}


async def _a_my_claims(db, tenant_id, user_id):
    me = await _me(db, tenant_id, user_id)
    rows = (
        await db.execute(select(m.HrmClaim.status, func.count()).where(m.HrmClaim.employee_id == me.id).group_by(m.HrmClaim.status))
    ).all()
    if not rows:
        return {"answer": "You have no expense claims. Make one under My HR.", "link": "/hrm?tab=me"}
    words = {"pending": "waiting", "paid": "paid back", "rejected": "turned down"}
    return {"answer": "Your claims: " + ", ".join(f"{n} {words.get(s, s)}" for s, n in rows) + ".", "link": "/hrm?tab=me"}


async def _a_who_on_leave(db, tenant_id, user_id):
    from app import hrm

    marks = await hrm.attendance_for(db, tenant_id, date.today())
    away = [r["full_name"] for r in marks if r["status"] == "leave"]
    if not away:
        return {"answer": "Nobody is on leave today.", "link": "/hrm?tab=leave"}
    return {"answer": f"On leave today ({len(away)}): " + ", ".join(away) + ".", "link": "/hrm?tab=leave"}


async def _a_pending_leave(db, tenant_id, user_id):
    rows = (
        await db.execute(
            select(m.HrmLeaveRequest.stage, func.count()).where(
                m.HrmLeaveRequest.tenant_id == tenant_id, m.HrmLeaveRequest.status == "pending"
            ).group_by(m.HrmLeaveRequest.stage)
        )
    ).all()
    if not rows:
        return {"answer": "No leave is waiting for a decision.", "link": "/hrm?tab=leave"}
    words = {"manager": "with managers", "hr": "with HR"}
    return {"answer": "Leave waiting: " + ", ".join(f"{n} {words.get(s, s)}" for s, n in rows) + ".", "link": "/hrm?tab=leave"}


async def _a_headcount(db, tenant_id, user_id):
    from app import hrm_org

    rows = await hrm_org.headcount(db, tenant_id)
    total = sum(r["filled"] for r in rows)
    parts = ", ".join(f"{r['department']} {r['filled']}" for r in rows)
    hiring = sum(r["hiring"] for r in rows)
    return {"answer": f"{total} active staff ({parts}). {hiring} role(s) being hired.", "link": "/hrm?tab=people"}


async def _a_contracts(db, tenant_id, user_id):
    from app import hrm_people

    alerts = await hrm_people.contract_alerts(db, tenant_id)
    ending = [c.get("employee_name") for c in alerts["contracts_ending"]]
    probation = [c.get("employee_name") for c in alerts["probation_due"]]
    if not ending and not probation:
        return {"answer": "No contract ends and no probation is due in the next 30 days.", "link": "/hrm?tab=contracts"}
    bits = []
    if ending:
        bits.append("contracts ending within 30 days: " + ", ".join(n or "?" for n in ending))
    if probation:
        bits.append("probation to confirm: " + ", ".join(n or "?" for n in probation))
    return {"answer": "; ".join(bits).capitalize() + ".", "link": "/hrm?tab=contracts"}


async def _a_signals(db, tenant_id, user_id):
    from app import hrm_insights

    rows = await hrm_insights.signals(db, tenant_id)
    if not rows:
        return {"answer": "No people signals right now.", "link": "/hrm?tab=people"}
    top = "; ".join(f"{r['name']}: {r['title'].lower()}" for r in rows[:5])
    more = f" and {len(rows) - 5} more" if len(rows) > 5 else ""
    return {"answer": f"{len(rows)} signal(s): {top}{more}. Each is a reason to talk, not a judgement.", "link": "/hrm?tab=people"}


async def _a_payroll_state(db, tenant_id, user_id):
    period = date.today().strftime("%Y-%m")
    run = (
        await db.execute(select(m.HrmPayrollRun).where(m.HrmPayrollRun.tenant_id == tenant_id, m.HrmPayrollRun.period == period))
    ).scalar_one_or_none()
    if run is None:
        return {"answer": f"The {period} payroll is not drawn up yet.", "link": "/hrm?tab=payroll"}
    words = {"draft": "drawn up and waiting for approval", "approved": "approved", "paid": "paid"}
    left = [w for w, at in (("staff", run.staff_paid_at), ("PAYE", run.paye_paid_at), ("SSNIT", run.ssnit_paid_at)) if at is None]
    tail = f" Still to pay: {', '.join(left)}." if run.status != "draft" and left else ""
    return {"answer": f"The {period} payroll is {words.get(run.status, run.status)}.{tail}", "link": "/hrm?tab=payroll"}


async def ask(db: AsyncSession, claims: dict, question: str) -> dict[str, Any]:
    from app import ai as ai_svc

    injection = ai_svc.find_injection(question)
    if injection:
        await ai_svc.record_query(
            db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), endpoint="hr_assistant",
            status="blocked", message=question, blocked_reason="prompt_injection",
        )
        raise HTTPException(status_code=400, detail="Question rejected by safety controls")
    out = await answer(db, claims, question)
    await ai_svc.record_query(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), endpoint="hr_assistant",
        status="ok" if out["intent"] else "unmatched", message=question, details={"intent": out["intent"]},
    )
    return out
