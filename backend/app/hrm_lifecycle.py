"""HR lifecycle: onboarding and offboarding checklists, exit interviews, benefits, career history,
OKRs, custom staff fields and succession plans.

None of this holds pay. Salary changes stay in hrm_pay_changes. Offboarding clearance does not end
employment by itself: HR still records the leaving date (hrm.end_employment) and final pay.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

ONBOARDING = [
    "Collect signed contract and ID copies",
    "Record SSNIT, TIN, Ghana Card and payment details",
    "Staff handbook read and accepted",
    "Issue equipment and uniform",
    "Create sign-in account and system access",
    "Assign mandatory training",
    "Set probation review date",
]
OFFBOARDING = [
    "Resignation or termination letter filed",
    "Handover of duties done",
    "Remove system access and sign-in account",
    "Exit interview held",
    "Final pay and leave settlement prepared",
]
KINDS = ("onboarding", "offboarding")
BENEFIT_KINDS = ("insurance", "pension", "welfare", "other")
CAREER_KINDS = ("promotion", "transfer", "confirmation", "other")
READINESS = ("ready_now", "one_two_years", "three_plus")
EXIT_REASONS = ("better_pay", "career_growth", "relocation", "personal", "management", "contract_end", "dismissal", "retirement", "other")


async def _emp(db, tenant_id, employee_id) -> m.HrmEmployee:
    from app import hrm

    return await hrm._employee(db, tenant_id, employee_id)


async def _audit(db, tenant_id, user_id, action, entity, entity_id, details):
    from app import hrm

    await hrm._audit(db, tenant_id, user_id, action, entity, entity_id, details)


def _iso(v):
    return v.isoformat() if v else None


# --- Checklists ---------------------------------------------------------------------------


def _task(t: m.HrmChecklistTask) -> dict:
    return {"id": t.id, "employee_id": t.employee_id, "kind": t.kind, "title": t.title, "due_on": _iso(t.due_on),
            "asset_id": t.asset_id, "done": t.done_on is not None, "done_on": _iso(t.done_on)}


async def tasks_for(db, tenant_id, employee_id, kind) -> list[m.HrmChecklistTask]:
    return list(
        (await db.execute(
            select(m.HrmChecklistTask).where(
                m.HrmChecklistTask.tenant_id == tenant_id, m.HrmChecklistTask.employee_id == employee_id,
                m.HrmChecklistTask.kind == kind,
            ).order_by(m.HrmChecklistTask.sort, m.HrmChecklistTask.created_at)
        )).scalars()
    )


async def checklist(db, tenant_id, employee_id, kind) -> dict:
    rows = await tasks_for(db, tenant_id, employee_id, kind)
    done = sum(1 for r in rows if r.done_on)
    out = {"kind": kind, "tasks": [_task(r) for r in rows], "done": done, "total": len(rows),
           "complete": bool(rows) and done == len(rows)}
    if kind == "offboarding":
        iv = (await db.execute(select(m.HrmExitInterview).where(m.HrmExitInterview.employee_id == employee_id))).scalar_one_or_none()
        out["exit_interview"] = exit_interview_out(iv) if iv else None
    return out


async def start_checklist(db, tenant_id, employee_id, kind, user_id) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Choose onboarding or offboarding")
    emp = await _emp(db, tenant_id, employee_id)
    if await tasks_for(db, tenant_id, employee_id, kind):
        raise HTTPException(status_code=409, detail="This checklist has already been started")
    titles = [(t, None) for t in (ONBOARDING if kind == "onboarding" else OFFBOARDING)]
    if kind == "offboarding":
        assets = (await db.execute(
            select(m.HrmAsset).where(
                m.HrmAsset.tenant_id == tenant_id, m.HrmAsset.employee_id == employee_id, m.HrmAsset.returned_on.is_(None)
            )
        )).scalars().all()
        titles += [(f"Recover {a.item}" + (f" ({a.serial})" if a.serial else ""), a.id) for a in assets]
    for i, (title, asset_id) in enumerate(titles):
        db.add(m.HrmChecklistTask(tenant_id=tenant_id, employee_id=employee_id, kind=kind, title=title, sort=i, asset_id=asset_id))
    await _audit(db, tenant_id, user_id, f"hrm_{kind}_started", "hrm_employee", emp.id, {"tasks": len(titles)})
    await db.flush()
    return await checklist(db, tenant_id, employee_id, kind)


async def add_task(db, tenant_id, employee_id, kind, title, due_on, user_id) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Choose onboarding or offboarding")
    await _emp(db, tenant_id, employee_id)
    text = require_honest_narrative(title, label="task", max_length=200)
    n = len(await tasks_for(db, tenant_id, employee_id, kind))
    db.add(m.HrmChecklistTask(tenant_id=tenant_id, employee_id=employee_id, kind=kind, title=text, sort=n, due_on=due_on))
    await db.flush()
    return await checklist(db, tenant_id, employee_id, kind)


async def set_task_done(db, tenant_id, task_id, done: bool, user_id) -> dict:
    t = await db.get(m.HrmChecklistTask, task_id)
    if t is None or t.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    if done and t.asset_id:
        asset = await db.get(m.HrmAsset, t.asset_id)
        if asset is not None and asset.returned_on is None:
            raise HTTPException(status_code=409, detail="Record the item as returned on the staff file first")
    t.done_on = date.today() if done else None
    t.done_by = user_id if done else None
    await _audit(db, tenant_id, user_id, "hrm_checklist_done" if done else "hrm_checklist_undone", "hrm_employee", t.employee_id, {"task": t.title})
    await db.flush()
    return await checklist(db, tenant_id, t.employee_id, t.kind)


async def overview(db, tenant_id) -> list[dict]:
    rows = (await db.execute(select(m.HrmChecklistTask).where(m.HrmChecklistTask.tenant_id == tenant_id))).scalars().all()
    people = {p.id: p for p in (await db.execute(select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id))).scalars()}
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r.employee_id, r.kind), []).append(r)
    out = []
    for (eid, kind), items in groups.items():
        done = sum(1 for i in items if i.done_on)
        if done == len(items):
            continue
        out.append({"employee_id": eid, "name": people[eid].full_name if eid in people else "", "kind": kind,
                    "done": done, "total": len(items)})
    return sorted(out, key=lambda r: (r["kind"], r["name"]))


# --- Exit interview -----------------------------------------------------------------------


def exit_interview_out(r: m.HrmExitInterview) -> dict:
    return {"id": r.id, "employee_id": r.employee_id, "held_on": _iso(r.held_on), "reason_category": r.reason_category,
            "would_return": r.would_return, "feedback": r.feedback}


async def save_exit_interview(db, tenant_id, employee_id, *, held_on, reason_category, would_return, feedback, user_id) -> dict:
    await _emp(db, tenant_id, employee_id)
    if reason_category not in EXIT_REASONS:
        raise HTTPException(status_code=422, detail="Choose the main reason for leaving")
    text = optional_honest_narrative(feedback, label="feedback", max_length=2000)
    row = (await db.execute(select(m.HrmExitInterview).where(m.HrmExitInterview.employee_id == employee_id))).scalar_one_or_none()
    if row is None:
        row = m.HrmExitInterview(tenant_id=tenant_id, employee_id=employee_id, held_on=held_on, reason_category=reason_category)
        db.add(row)
    row.held_on, row.reason_category, row.would_return, row.feedback, row.held_by = held_on, reason_category, would_return, text, user_id
    await _audit(db, tenant_id, user_id, "hrm_exit_interview_saved", "hrm_employee", employee_id, {"reason": reason_category})
    await db.flush()
    return exit_interview_out(row)


# --- Benefits -----------------------------------------------------------------------------


def _benefit(b: m.HrmBenefit) -> dict:
    return {"id": b.id, "employee_id": b.employee_id, "kind": b.kind, "name": b.name, "provider": b.provider,
            "policy_number": b.policy_number, "starts_on": _iso(b.starts_on), "ends_on": _iso(b.ends_on),
            "note": b.note, "active": b.ends_on is None or b.ends_on >= date.today()}


async def add_benefit(db, tenant_id, employee_id, *, kind, name, provider, policy_number, starts_on, ends_on, note, user_id) -> dict:
    await _emp(db, tenant_id, employee_id)
    if kind not in BENEFIT_KINDS:
        raise HTTPException(status_code=422, detail="Choose the kind of benefit")
    if ends_on and ends_on < starts_on:
        raise HTTPException(status_code=422, detail="The benefit ends before it starts")
    row = m.HrmBenefit(
        tenant_id=tenant_id, employee_id=employee_id, kind=kind,
        name=require_honest_narrative(name, label="benefit name", max_length=160),
        provider=optional_honest_narrative(provider, label="provider", max_length=160),
        policy_number=optional_honest_narrative(policy_number, label="policy number", max_length=80),
        starts_on=starts_on, ends_on=ends_on, note=optional_honest_narrative(note, label="note", max_length=255), created_by=user_id,
    )
    db.add(row)
    await _audit(db, tenant_id, user_id, "hrm_benefit_added", "hrm_employee", employee_id, {"benefit": row.name})
    await db.flush()
    return _benefit(row)


async def end_benefit(db, tenant_id, benefit_id, ends_on, user_id) -> dict:
    row = await db.get(m.HrmBenefit, benefit_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Benefit not found")
    if ends_on < row.starts_on:
        raise HTTPException(status_code=422, detail="The benefit ends before it starts")
    row.ends_on = ends_on
    await _audit(db, tenant_id, user_id, "hrm_benefit_ended", "hrm_employee", row.employee_id, {"benefit": row.name})
    await db.flush()
    return _benefit(row)


async def benefits_for(db, tenant_id, employee_id) -> list[dict]:
    rows = (await db.execute(
        select(m.HrmBenefit).where(m.HrmBenefit.tenant_id == tenant_id, m.HrmBenefit.employee_id == employee_id)
        .order_by(m.HrmBenefit.starts_on.desc())
    )).scalars().all()
    return [_benefit(r) for r in rows]


# --- Career history -----------------------------------------------------------------------


def _event(e: m.HrmCareerEvent) -> dict:
    return {"id": e.id, "kind": e.kind, "effective_on": _iso(e.effective_on), "from_job_title": e.from_job_title,
            "to_job_title": e.to_job_title, "from_department": e.from_department, "to_department": e.to_department, "note": e.note}


async def record_career_event(db, tenant_id, employee_id, *, kind, effective_on, to_job_title, to_department, note, user_id) -> dict:
    emp = await _emp(db, tenant_id, employee_id)
    if kind not in CAREER_KINDS:
        raise HTTPException(status_code=422, detail="Choose promotion, transfer, confirmation or other")
    if emp.status != "active":
        raise HTTPException(status_code=409, detail="This person has left")
    if effective_on > date.today():
        raise HTTPException(status_code=422, detail="Record the change on the day it takes effect")
    title = optional_honest_narrative(to_job_title, label="new job title", max_length=120)
    dept = optional_honest_narrative(to_department, label="new department", max_length=120)
    if kind in ("promotion", "transfer") and not (title or dept):
        raise HTTPException(status_code=422, detail="Give the new job title or department")
    ev = m.HrmCareerEvent(
        tenant_id=tenant_id, employee_id=employee_id, kind=kind, effective_on=effective_on,
        from_job_title=emp.job_title, to_job_title=title, from_department=emp.department, to_department=dept,
        note=optional_honest_narrative(note, label="note", max_length=255), created_by=user_id,
    )
    db.add(ev)
    _apply(emp, ev)
    await _audit(db, tenant_id, user_id, "hrm_career_event", "hrm_employee", employee_id, {"kind": kind, "to_job_title": title, "to_department": dept})
    await db.flush()
    return _event(ev)


def _apply(emp: m.HrmEmployee, ev: m.HrmCareerEvent) -> None:
    if ev.to_job_title:
        emp.job_title = ev.to_job_title
    if ev.to_department:
        emp.department = ev.to_department


async def career_history(db, tenant_id, employee_id) -> list[dict]:
    rows = (await db.execute(
        select(m.HrmCareerEvent).where(m.HrmCareerEvent.tenant_id == tenant_id, m.HrmCareerEvent.employee_id == employee_id)
        .order_by(m.HrmCareerEvent.effective_on.desc(), m.HrmCareerEvent.created_at.desc())
    )).scalars().all()
    return [_event(r) for r in rows]


# --- OKRs ---------------------------------------------------------------------------------


def _okr(o: m.HrmObjective, children=None) -> dict:
    target = float(o.target) if o.target is not None else None
    cur = float(o.current or 0)
    pct = None
    if o.kind == "key_result" and target:
        pct = round(min(cur / target * 100, 100), 1)
    out = {"id": o.id, "kind": o.kind, "level": o.level, "parent_id": o.parent_id, "employee_id": o.employee_id,
           "department": o.department, "period": o.period, "title": o.title, "unit": o.unit,
           "target": money_json(target) if target is not None else None, "current": money_json(cur),
           "status": o.status, "progress": pct}
    if children is not None:
        out["key_results"] = children
        vals = [c["progress"] for c in children if c["progress"] is not None]
        out["progress"] = round(sum(vals) / len(vals), 1) if vals else None
    return out


async def create_objective(db, tenant_id, *, kind, level, period, title, employee_id, department, parent_id, unit, target, user_id) -> dict:
    if kind not in ("objective", "key_result") or level not in ("company", "department", "employee"):
        raise HTTPException(status_code=422, detail="Unknown objective kind or level")
    parent = None
    if kind == "key_result":
        if not parent_id:
            raise HTTPException(status_code=422, detail="A key result belongs under an objective")
        parent = await db.get(m.HrmObjective, parent_id)
        if parent is None or parent.tenant_id != tenant_id or parent.kind != "objective":
            raise HTTPException(status_code=404, detail="Objective not found")
        if target is None or target <= 0:
            raise HTTPException(status_code=422, detail="A key result needs a target above zero")
        level, period, employee_id, department = parent.level, parent.period, parent.employee_id, parent.department
    else:
        if level == "employee":
            if not employee_id:
                raise HTTPException(status_code=422, detail="Choose whose objective this is")
            await _emp(db, tenant_id, employee_id)
        elif level == "department":
            department = require_honest_narrative(department, label="department", max_length=120)
            employee_id = None
        else:
            employee_id = department = None
        if parent_id:
            parent = await db.get(m.HrmObjective, parent_id)
            if parent is None or parent.tenant_id != tenant_id or parent.kind != "objective":
                raise HTTPException(status_code=404, detail="Parent objective not found")
    row = m.HrmObjective(
        tenant_id=tenant_id, kind=kind, level=level, parent_id=parent_id, employee_id=employee_id, department=department,
        period=require_honest_narrative(period, label="period", max_length=16),
        title=require_honest_narrative(title, label="title", max_length=200),
        unit=optional_honest_narrative(unit, label="unit", max_length=24), target=target, created_by=user_id,
    )
    db.add(row)
    await _audit(db, tenant_id, user_id, "hrm_objective_created", "hrm_objective", row.id, {"title": row.title, "kind": kind})
    await db.flush()
    return _okr(row)


async def update_objective(db, tenant_id, objective_id, *, current, status, user_id) -> dict:
    row = await db.get(m.HrmObjective, objective_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Objective not found")
    if current is not None:
        if row.kind != "key_result":
            raise HTTPException(status_code=422, detail="Progress is recorded on key results")
        row.current = current
    if status is not None:
        if status not in ("open", "done", "dropped"):
            raise HTTPException(status_code=422, detail="Unknown status")
        row.status = status
    await _audit(db, tenant_id, user_id, "hrm_objective_updated", "hrm_objective", row.id, {"current": current, "status": status})
    await db.flush()
    return _okr(row)


async def list_objectives(db, tenant_id, *, period=None, employee_id=None) -> list[dict]:
    q = select(m.HrmObjective).where(m.HrmObjective.tenant_id == tenant_id)
    if period:
        q = q.where(m.HrmObjective.period == period)
    rows = (await db.execute(q.order_by(m.HrmObjective.created_at))).scalars().all()
    krs: dict[str, list] = {}
    for r in rows:
        if r.kind == "key_result" and r.parent_id:
            krs.setdefault(r.parent_id, []).append(_okr(r))
    out = [_okr(r, krs.get(r.id, [])) for r in rows if r.kind == "objective"]
    if employee_id:
        out = [o for o in out if o["employee_id"] == employee_id]
    return out


# --- Custom fields ------------------------------------------------------------------------


async def create_field(db, tenant_id, label, kind, user_id) -> dict:
    if kind not in ("text", "number", "date"):
        raise HTTPException(status_code=422, detail="Choose text, number or date")
    text = require_honest_narrative(label, label="label", max_length=80)
    dup = (await db.execute(select(m.HrmCustomField).where(m.HrmCustomField.tenant_id == tenant_id, m.HrmCustomField.label == text))).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status_code=409, detail="A field with this name already exists")
    f = m.HrmCustomField(tenant_id=tenant_id, label=text, kind=kind)
    db.add(f)
    await db.flush()
    return {"id": f.id, "label": f.label, "kind": f.kind, "active": True}


async def list_fields(db, tenant_id) -> list[m.HrmCustomField]:
    return list((await db.execute(select(m.HrmCustomField).where(m.HrmCustomField.tenant_id == tenant_id, m.HrmCustomField.active.is_(True)).order_by(m.HrmCustomField.label))).scalars())


async def retire_field(db, tenant_id, field_id) -> None:
    f = await db.get(m.HrmCustomField, field_id)
    if f is None or f.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Field not found")
    f.active = False
    await db.flush()


async def set_custom_value(db, tenant_id, employee_id, field_id, value, user_id) -> None:
    await _emp(db, tenant_id, employee_id)
    f = await db.get(m.HrmCustomField, field_id)
    if f is None or f.tenant_id != tenant_id or not f.active:
        raise HTTPException(status_code=404, detail="Field not found")
    text = (value or "").strip()
    row = (await db.execute(select(m.HrmCustomValue).where(m.HrmCustomValue.employee_id == employee_id, m.HrmCustomValue.field_id == field_id))).scalar_one_or_none()
    if not text:
        if row is not None:
            await db.delete(row)
        await db.flush()
        return
    if f.kind == "number":
        try:
            float(text)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{f.label} must be a number") from None
    elif f.kind == "date":
        try:
            date.fromisoformat(text)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{f.label} must be a date (YYYY-MM-DD)") from None
    else:
        text = require_honest_narrative(text, label=f.label, max_length=255)
    if row is None:
        db.add(m.HrmCustomValue(tenant_id=tenant_id, employee_id=employee_id, field_id=field_id, value=text))
    else:
        row.value = text
    await _audit(db, tenant_id, user_id, "hrm_custom_value_set", "hrm_employee", employee_id, {"field": f.label})
    await db.flush()


async def custom_values(db, tenant_id, employee_id) -> list[dict]:
    await _emp(db, tenant_id, employee_id)
    vals = {v.field_id: v.value for v in (await db.execute(select(m.HrmCustomValue).where(m.HrmCustomValue.employee_id == employee_id))).scalars()}
    return [{"field_id": f.id, "label": f.label, "kind": f.kind, "value": vals.get(f.id)} for f in await list_fields(db, tenant_id)]


# --- Succession ---------------------------------------------------------------------------


async def save_succession(db, tenant_id, *, position, incumbent_id, successor_id, readiness, note, user_id) -> dict:
    if readiness not in READINESS:
        raise HTTPException(status_code=422, detail="Choose how soon they could step in")
    s = await _emp(db, tenant_id, successor_id)
    if incumbent_id:
        await _emp(db, tenant_id, incumbent_id)
        if incumbent_id == successor_id:
            raise HTTPException(status_code=422, detail="Someone cannot succeed themselves")
    row = m.HrmSuccession(
        tenant_id=tenant_id, position=require_honest_narrative(position, label="position", max_length=160),
        incumbent_id=incumbent_id, successor_id=successor_id, readiness=readiness,
        note=optional_honest_narrative(note, label="note", max_length=255),
    )
    db.add(row)
    await _audit(db, tenant_id, user_id, "hrm_succession_added", "hrm_employee", successor_id, {"position": row.position})
    await db.flush()
    return {"id": row.id, "position": row.position, "incumbent_id": incumbent_id, "successor_id": s.id,
            "successor": s.full_name, "readiness": readiness, "note": row.note}


async def list_succession(db, tenant_id) -> list[dict]:
    people = {p.id: p.full_name for p in (await db.execute(select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id))).scalars()}
    rows = (await db.execute(select(m.HrmSuccession).where(m.HrmSuccession.tenant_id == tenant_id).order_by(m.HrmSuccession.position))).scalars().all()
    return [{"id": r.id, "position": r.position, "incumbent_id": r.incumbent_id, "incumbent": people.get(r.incumbent_id),
             "successor_id": r.successor_id, "successor": people.get(r.successor_id), "readiness": r.readiness, "note": r.note} for r in rows]


async def remove_succession(db, tenant_id, row_id) -> None:
    r = await db.get(m.HrmSuccession, row_id)
    if r is None or r.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.delete(r)
    await db.flush()
