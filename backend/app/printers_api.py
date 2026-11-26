"""HTTP API for tenant printers, jobs, and print-agent pairing."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import printers as printers_svc
from app import receipt_print as receipt_svc
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, UuidIdValue
from app.security import current_claims, require_permission

router = APIRouter(prefix="/printers", tags=["printers"])


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


def _agent_token(
    authorization: str | None = Header(default=None),
    x_print_agent_token: str | None = Header(default=None, alias="X-Print-Agent-Token"),
) -> str:
    if x_print_agent_token:
        return x_print_agent_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="Print agent token required")


@router.get("/capabilities")
async def printer_capabilities(
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    return env(printers_svc.capabilities(getattr(tenant, "industry", None) if tenant else None))


@router.get("")
async def list_printers(
    store_id: str | None = None,
    purpose: str | None = None,
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    await printers_svc.assert_printer_store_access(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        role=claims.get("role"),
        store_id=store_id,
    )
    industry = await printers_svc.load_tenant_industry(db, claims["tenant_id"])
    rows = await printers_svc.list_printers(
        db, tenant_id=claims["tenant_id"], store_id=store_id, purpose=purpose
    )
    listed = []
    for row in rows:
        data = printers_svc.serialize_printer(row)
        data["purposes"] = printers_svc.visible_purposes_for_industry(row.purposes, industry)
        listed.append(data)
    return env(listed)


@router.post("")
async def create_printer(
    payload: printers_svc.PrinterCreate,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    await printers_svc.assert_printer_store_access(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        role=claims.get("role"),
        store_id=payload.store_id,
    )
    row = await printers_svc.create_printer(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), payload=payload
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="printer_create",
        entity="printer",
        entity_id=row.id,
        details={"name": row.name, "connection_type": row.connection_type, "purposes": row.purposes},
    )
    await db.commit()
    return env(printers_svc.serialize_printer(row), "Printer saved")


@router.get("/receipt-email-sms")
async def get_receipt_email_sms(
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    return env({"show_email_sms": printers_svc.pos_show_receipt_email_sms(tenant)})


@router.patch("/receipt-email-sms")
async def patch_receipt_email_sms(
    payload: printers_svc.ReceiptEmailSmsUpdate,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    enabled = printers_svc.set_pos_show_receipt_email_sms(tenant, payload.show_email_sms)
    await db.commit()
    return env({"show_email_sms": enabled})


@router.patch("/{printer_id}")
async def patch_printer(
    printer_id: str,
    payload: printers_svc.PrinterUpdate,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await printers_svc.update_printer(
        db, tenant_id=claims["tenant_id"], printer_id=printer_id, payload=payload
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="printer_update",
        entity="printer",
        entity_id=row.id,
        details={"name": row.name, "is_enabled": row.is_enabled},
    )
    await db.commit()
    return env(printers_svc.serialize_printer(row), "Printer updated")


@router.delete("/{printer_id}")
async def remove_printer(
    printer_id: str,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await printers_svc.delete_printer(
        db, tenant_id=claims["tenant_id"], printer_id=printer_id
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="printer_delete",
        entity="printer",
        entity_id=row.id,
        details={"name": row.name, "connection_type": row.connection_type},
    )
    await db.commit()
    return env({"id": row.id, "name": row.name}, "Printer deleted")


@router.post("/{printer_id}/test")
async def test_printer(
    printer_id: str,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    printer = await db.get(m.Printer, printer_id)
    if not printer or printer.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="Printer not found")
    job = await printers_svc.enqueue_test_print(
        db, tenant_id=claims["tenant_id"], printer=printer, user_id=claims.get("sub")
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="printer_test",
        entity="print_job",
        entity_id=job.id,
        details={"printer_id": printer.id, "status": job.status},
    )
    await db.commit()
    return env(printers_svc.serialize_job(job, include_payload=True), "Test print queued")


ReceiptSource = Literal[
    "pos_sale",
    "restaurant_order",
    "bakery_sale",
    "bakery_order_payment",
    "bakery_customer_payment",
    "hotel_payment",
    "hotel_shop_sale",
    "gym_payment",
    "gym_sale",
    "fmcg_payment",
    "customer_payment",
    "layaway_payment",
]

# The hotel request each hotel receipt belongs to, for the hotel staff job rules.
_HOTEL_PAYMENT_PATHS = {
    "hotel_payment": "/hotel/folios/x/payments",
    "hotel_shop_sale": "/hotel/shop/sales",
    "customer_payment": "/hotel/invoices/x/payments",
}


class ReceiptPrintBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: ReceiptSource
    source_id: UuidIdValue
    # auto: straight after payment. print: asked again. retry: resend a failed copy. reprint: new copy.
    mode: Literal["auto", "print", "retry", "reprint"] = "auto"
    terminal_id: str | None = Field(default=None, max_length=64)
    cash_tendered: NonNegativeMoneyValue | None = None


class TerminalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=80)
    receipt_printer_id: UuidIdValue | None = None
    auto_print: bool = True


async def _require_receipt_access(
    source_type: str, request: Request, claims: dict, db: AsyncSession, action: str = "read"
) -> None:
    """Printing the first copy needs to see the payment; another copy needs to be able to take one."""
    refused: HTTPException | None = None
    for module in receipt_svc.SOURCE_MODULES[source_type]:
        try:
            await require_permission(module, action)(request=request, claims=claims, db=db)
        except HTTPException as exc:
            refused = exc
            continue
        if module == "hotel":
            from app import hotel_jobs

            job = await hotel_jobs.job_role(db, claims.get("tenant_id"), claims.get("role"))
            hotel_jobs.enforce(job, "POST", _HOTEL_PAYMENT_PATHS[source_type])
        return
    raise refused or HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/receipts")
async def print_payment_receipt(
    payload: ReceiptPrintBody,
    request: Request,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    """Print the receipt of a saved payment. Safe to call twice; never creates or changes a payment."""
    await _require_receipt_access(
        payload.source_type, request, claims, db, "write" if payload.mode in {"retry", "reprint"} else "read"
    )
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    queued_before = payload.mode == "retry" and await receipt_svc.receipt_status(
        db, tenant_id=claims["tenant_id"], source_type=payload.source_type, source_id=payload.source_id
    )
    if queued_before:
        jobs = await receipt_svc.retry_receipt(
            db,
            tenant=tenant,
            source_type=payload.source_type,
            source_id=payload.source_id,
            user_id=claims.get("sub"),
        )
        receipt = await receipt_svc.build_receipt(
            db, tenant=tenant, source_type=payload.source_type, source_id=payload.source_id
        )
        data = {"receipt": receipt_svc._public(receipt), "jobs": jobs, "auto_print": True}
    else:
        data = await receipt_svc.print_receipt(
            db,
            tenant=tenant,
            source_type=payload.source_type,
            source_id=payload.source_id,
            mode=payload.mode,
            terminal_id=payload.terminal_id,
            cash_tendered=payload.cash_tendered,
            user_id=claims.get("sub"),
        )
    if payload.mode in {"retry", "reprint"}:
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims["sub"],
            module="printers",
            action=f"print_{payload.mode}",
            entity=payload.source_type,
            entity_id=payload.source_id,
            details={"job_ids": [j["id"] for j in data["jobs"]]},
        )
    if not any(job["status"] == "printed" for job in data["jobs"]):
        # For the manual "Open print window" button when no printer can print by itself.
        data["fallback"] = await receipt_svc.fallback_slip(
            db,
            tenant=tenant,
            source_type=payload.source_type,
            source_id=payload.source_id,
            cash_tendered=payload.cash_tendered,
        )
    await db.commit()
    return env(data, "Receipt print requested")


@router.get("/receipts")
async def payment_receipt_status(
    source_type: ReceiptSource,
    source_id: UuidIdValue,
    request: Request,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    await _require_receipt_access(source_type, request, claims, db)
    return env(
        {
            "jobs": await receipt_svc.receipt_status(
                db, tenant_id=claims["tenant_id"], source_type=source_type, source_id=source_id
            )
        }
    )


@router.get("/terminals")
async def list_print_terminals(
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    return env(receipt_svc.list_terminals(tenant))


@router.get("/terminals/{terminal_id}")
async def get_print_terminal(
    terminal_id: str,
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    return env(receipt_svc.terminal_settings(tenant, terminal_id[:64]))


@router.put("/terminals/{terminal_id}")
async def put_print_terminal(
    terminal_id: str,
    payload: TerminalBody,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(m.Tenant, claims["tenant_id"])
    data = await receipt_svc.save_terminal(
        db,
        tenant=tenant,
        terminal_id=terminal_id[:64],
        name=payload.name,
        receipt_printer_id=payload.receipt_printer_id,
        auto_print=payload.auto_print,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="print_terminal_saved",
        entity="terminal",
        entity_id=terminal_id[:36],
        details={"receipt_printer_id": payload.receipt_printer_id, "auto_print": payload.auto_print},
    )
    await db.commit()
    return env(data, "Till printer saved")


@router.get("/jobs")
async def list_print_jobs(
    source_id: str | None = None,
    status: str | None = None,
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await printers_svc.list_jobs(
        db, tenant_id=claims["tenant_id"], source_id=source_id, status=status
    )
    return env([printers_svc.serialize_job(r) for r in rows])


@router.get("/jobs/{job_id}")
async def get_print_job(
    job_id: str,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(m.PrintJob, job_id)
    if not job or job.tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=404, detail="Print job not found")
    return env(printers_svc.serialize_job(job, include_payload=True))


@router.post("/jobs/{job_id}/retry")
async def retry_print_job(
    job_id: str,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    job = await printers_svc.retry_job(
        db, tenant_id=claims["tenant_id"], job_id=job_id, user_id=claims.get("sub")
    )
    await printers_svc.deliver_now(db, job)
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="print_retry",
        entity="print_job",
        entity_id=job.id,
        details={"source_id": job.source_id, "status": job.status},
    )
    await db.commit()
    return env(printers_svc.serialize_job(job), "Print job retried (same sale)")


@router.post("/jobs/{job_id}/browser-ack")
async def browser_ack_job(
    job_id: str,
    payload: printers_svc.BrowserAckBody,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    job = await printers_svc.ack_browser_job(
        db,
        tenant_id=claims["tenant_id"],
        job_id=job_id,
        status=payload.status,
        user_id=claims.get("sub"),
        detail=payload.detail,
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="print_browser_ack",
        entity="print_job",
        entity_id=job.id,
        details={"status": job.status},
    )
    await db.commit()
    return env(printers_svc.serialize_job(job), "Browser print acknowledged")


@router.post("/reprint")
async def reprint_document(
    payload: printers_svc.ReprintBody,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    jobs = await printers_svc.reprint_source(
        db,
        tenant_id=claims["tenant_id"],
        source_type=payload.source_type,
        source_id=payload.source_id,
        purposes=payload.purposes,
        user_id=claims.get("sub"),
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="print_reprint",
        entity=payload.source_type,
        entity_id=payload.source_id,
        details={"job_ids": [j.id for j in jobs]},
    )
    await db.commit()
    return env(
        [printers_svc.serialize_job(j) for j in jobs],
        "Reprint queued (same document, new jobs)",
    )


@router.post("/agents/pairing-codes")
async def create_pairing_code(
    payload: printers_svc.PairingCodeCreate,
    claims=Depends(require_permission("printers", "write")),
    db: AsyncSession = Depends(get_db),
):
    agent, code = await printers_svc.issue_pairing_code(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), payload=payload
    )
    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        module="printers",
        action="agent_pairing_issued",
        entity="print_agent",
        entity_id=agent.id,
        details={"label": agent.label, "store_id": agent.store_id},
    )
    await db.commit()
    data = printers_svc.serialize_agent(agent)
    data["pairing_code"] = code
    data["expires_in_minutes"] = printers_svc.PAIRING_TTL_MINUTES
    data["pairing_code_shown_once"] = True
    return env(data, "Pairing code created — install it on the till agent")


@router.get("/agents")
async def list_agents(
    claims=Depends(require_permission("printers", "read")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(m.PrintAgent)
            .where(m.PrintAgent.tenant_id == claims["tenant_id"])
            .order_by(m.PrintAgent.created_at.desc())
        )
    ).scalars().all()
    return env([printers_svc.serialize_agent(r) for r in rows])


@router.post("/agents/pair", include_in_schema=True)
async def pair_print_agent(
    payload: printers_svc.AgentPairBody,
    db: AsyncSession = Depends(get_db),
):
    """Public to the till only via short-lived pairing code (not a user session)."""
    agent, token = await printers_svc.pair_agent(
        db, pairing_code=payload.pairing_code, label=payload.label
    )
    await audit_svc.record_event(
        db,
        tenant_id=agent.tenant_id,
        user_id=None,
        module="printers",
        action="agent_paired",
        entity="print_agent",
        entity_id=agent.id,
        details={"label": agent.label},
    )
    await db.commit()
    data = printers_svc.serialize_agent(agent, include_secret=token)
    return env(data, "Print agent paired — store the token on the till; it is not shown again")


@router.get("/agent/jobs")
async def agent_poll_jobs(
    limit: int = Query(default=10, ge=1, le=50),
    token: str = Depends(_agent_token),
    db: AsyncSession = Depends(get_db),
):
    agent = await printers_svc.authenticate_agent(db, token)
    jobs = await printers_svc.claim_jobs(db, agent=agent, limit=limit)
    await db.commit()
    return env(
        [
            await printers_svc.agent_job(db, j)
            for j in jobs
        ]
    )


@router.post("/agent/jobs/{job_id}/complete")
async def agent_complete_job(
    job_id: str,
    payload: printers_svc.JobCompleteBody,
    token: str = Depends(_agent_token),
    db: AsyncSession = Depends(get_db),
):
    agent = await printers_svc.authenticate_agent(db, token)
    job = await db.get(m.PrintJob, job_id)
    if not job or job.tenant_id != agent.tenant_id:
        raise HTTPException(status_code=404, detail="Print job not found")
    if job.claimed_by_agent_id and job.claimed_by_agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Job is claimed by another agent")
    updated = await printers_svc.complete_job(
        db,
        job=job,
        status=payload.status,
        detail=payload.detail,
        actor_id=None,
        agent=agent,
    )
    await db.commit()
    return env(printers_svc.serialize_job(updated), "Print job updated")
