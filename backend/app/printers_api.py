"""HTTP API for tenant printers, jobs, and print-agent pairing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import printers as printers_svc
from app.db import get_db
from app.security import require_permission

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
async def printer_capabilities(claims=Depends(require_permission("printers", "read"))):
    return env(printers_svc.capabilities())


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
    rows = await printers_svc.list_printers(
        db, tenant_id=claims["tenant_id"], store_id=store_id, purpose=purpose
    )
    return env([printers_svc.serialize_printer(r) for r in rows])


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
            printers_svc.serialize_job(j, include_payload=True)
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
