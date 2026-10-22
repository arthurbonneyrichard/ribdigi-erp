"""Help & Support and software-owner Support Desk routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app import support_tickets as svc
from app.db import get_db
from app.security import current_claims

router = APIRouter(prefix="/support", tags=["support"])

PriorityValue = Literal["low", "normal", "high", "urgent"]
StatusValue = Literal["new", "in_progress", "waiting_for_tenant", "resolved", "closed"]


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


def actor_from(request: Request, claims: dict) -> dict:
    return {
        "user_id": claims.get("sub"),
        "tenant_id": claims.get("tenant_id"),
        "role": claims.get("role") or "",
        "ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:255],
    }


def _reject_read_only(claims: dict) -> None:
    if claims.get("read_only"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_READ_ONLY",
                "message": "Trial expired; account is read-only during the grace period. Activate to restore write access.",
            },
        )


def require_support(action: str):
    async def dep(claims: dict = Depends(current_claims)) -> dict:
        if action not in {"view_own", "view_tenant", "view_all"}:
            _reject_read_only(claims)
        if not svc.support_can(claims, action):
            raise HTTPException(status_code=403, detail=f"Missing permission: support:{action}")
        return claims

    return dep


async def require_ticket_reader(claims: dict = Depends(current_claims)) -> dict:
    if svc.support_can(claims, "view_own") or svc.support_can(claims, "view_tenant"):
        return claims
    if svc.support_can(claims, "view_all"):
        return claims
    raise HTTPException(status_code=403, detail="Missing permission: support:view_own")


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    description: str
    category: str
    priority: PriorityValue = "normal"


class ReplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: StatusValue | None = None
    priority: PriorityValue | None = None
    category: str | None = None
    assignee_user_id: str | None = None
    assignee_set: bool = False

    @model_validator(mode="before")
    @classmethod
    def mark_assignee(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            data["assignee_set"] = "assignee_user_id" in data
        return data


class RecipientBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class RecipientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str | None = None
    is_active: bool | None = None


async def _read_upload(upload: UploadFile) -> bytes:
    max_bytes = int(svc.settings.SUPPORT_ATTACHMENT_MAX_BYTES or 10_000_000)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=422, detail="File is too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/categories")
async def support_categories(
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
):
    from app import models as m

    tenant = await db.get(m.Tenant, claims["tenant_id"])
    return env(
        {
            "categories": svc.categories_for(tenant),
            "priorities": list(svc.PRIORITIES),
            "statuses": list(svc.STATUSES),
        }
    )


@router.get("/tickets")
async def support_ticket_list(
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    data = await svc.list_tickets(
        db,
        claims,
        desk=False,
        status=status,
        priority=priority,
        category=category,
        assignee=None,
        q=q,
        from_date=None,
        to_date=None,
        limit=limit,
        offset=offset,
    )
    return env(data)


@router.post("/tickets")
async def support_ticket_create(
    body: TicketCreate,
    request: Request,
    claims: dict = Depends(require_support("create")),
    db: AsyncSession = Depends(get_db),
):
    await svc.enforce_rate_limit("create", claims["sub"])
    ticket = await svc.create_ticket(
        db,
        claims,
        actor_from(request, claims),
        subject=body.subject,
        description=body.description,
        category=body.category,
        priority=body.priority,
    )
    await db.commit()
    svc.enqueue_support_delivery()
    detail = await svc.ticket_detail(db, ticket, desk=False, include_internal=False)
    return env(detail, "Ticket created")


@router.get("/tickets/by-reference/{reference}")
async def support_ticket_by_reference(
    reference: str,
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket_by_reference(db, claims, reference)
    include_internal = svc.support_can(claims, "internal_note") and svc.support_can(claims, "view_all")
    return env(await svc.ticket_detail(db, ticket, desk=include_internal, include_internal=include_internal))


@router.get("/tickets/{ticket_id}")
async def support_ticket_get(
    ticket_id: str,
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    include_internal = svc.support_can(claims, "internal_note") and svc.support_can(claims, "view_all")
    return env(
        await svc.ticket_detail(db, ticket, desk=include_internal, include_internal=include_internal)
    )


@router.post("/tickets/{ticket_id}/replies")
async def support_ticket_reply(
    ticket_id: str,
    body: ReplyBody,
    request: Request,
    claims: dict = Depends(require_support("reply")),
    db: AsyncSession = Depends(get_db),
):
    await svc.enforce_rate_limit("reply", claims["sub"])
    ticket = await svc.require_ticket(db, claims, ticket_id)
    await svc.add_public_reply(
        db,
        claims,
        actor_from(request, claims),
        ticket,
        body.body,
        from_staff=svc.support_can(claims, "view_all"),
    )
    await db.commit()
    svc.enqueue_support_delivery()
    return env(await svc.ticket_detail(db, ticket, desk=False, include_internal=False), "Reply sent")


@router.post("/tickets/{ticket_id}/close")
async def support_ticket_close(
    ticket_id: str,
    request: Request,
    claims: dict = Depends(require_support("close")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATUS_TRANSITION", "message": "This ticket is already closed"},
        )
    await svc.apply_status(db, actor_from(request, claims), ticket, "closed")
    await db.commit()
    svc.enqueue_support_delivery()
    return env(await svc.ticket_detail(db, ticket, desk=False, include_internal=False), "Ticket closed")


@router.post("/tickets/{ticket_id}/attachments")
async def support_ticket_upload(
    ticket_id: str,
    request: Request,
    file: UploadFile = File(...),
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
):
    _reject_read_only(claims)
    if not (svc.support_can(claims, "create") or svc.support_can(claims, "reply")):
        raise HTTPException(status_code=403, detail="Missing permission: support:reply")
    await svc.enforce_rate_limit("reply", claims["sub"])
    ticket = await svc.require_ticket(db, claims, ticket_id)
    data = await _read_upload(file)
    row = await svc.save_attachment(
        db,
        actor_from(request, claims),
        ticket,
        filename=file.filename or "attachment",
        data=data,
    )
    await db.commit()
    return env(svc._attachment_dict(row), "Attachment saved")


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}")
async def support_ticket_download(
    ticket_id: str,
    attachment_id: str,
    claims: dict = Depends(require_ticket_reader),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    data, content_type, filename = await svc.read_attachment(db, ticket, attachment_id)
    ascii_name = filename.encode("ascii", "ignore").decode() or "attachment"
    ascii_name = ascii_name.replace('"', "")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/desk/categories")
async def desk_categories(claims: dict = Depends(require_support("view_all"))):
    _ = claims
    return env(
        {
            "categories": svc.categories_for(None, all_categories=True),
            "priorities": list(svc.PRIORITIES),
            "statuses": list(svc.STATUSES),
        }
    )


@router.get("/desk/counts")
async def desk_counts(
    claims: dict = Depends(require_support("view_all")),
    db: AsyncSession = Depends(get_db),
):
    _ = claims
    return env(await svc.desk_counts(db))


@router.get("/desk/staff")
async def desk_staff(
    claims: dict = Depends(require_support("view_all")),
    db: AsyncSession = Depends(get_db),
):
    _ = claims
    return env(await svc.list_staff(db))


@router.get("/desk/tickets")
async def desk_ticket_list(
    claims: dict = Depends(require_support("view_all")),
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    assignee: str | None = None,
    q: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    industry: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    data = await svc.list_tickets(
        db,
        claims,
        desk=True,
        status=status,
        priority=priority,
        category=category,
        assignee=assignee,
        q=q,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
        industry=industry,
    )
    return env(data)


@router.get("/desk/tickets/{ticket_id}")
async def desk_ticket_get(
    ticket_id: str,
    claims: dict = Depends(require_support("view_all")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    include_internal = svc.support_can(claims, "internal_note")
    return env(await svc.ticket_detail(db, ticket, desk=True, include_internal=include_internal))


@router.post("/desk/tickets/{ticket_id}/replies")
async def desk_ticket_reply(
    ticket_id: str,
    body: ReplyBody,
    request: Request,
    claims: dict = Depends(require_support("reply")),
    db: AsyncSession = Depends(get_db),
):
    if not svc.support_can(claims, "view_all"):
        raise HTTPException(status_code=403, detail="Missing permission: support:view_all")
    await svc.enforce_rate_limit("reply", claims["sub"])
    ticket = await svc.require_ticket(db, claims, ticket_id)
    await svc.add_public_reply(
        db,
        claims,
        actor_from(request, claims),
        ticket,
        body.body,
        from_staff=True,
    )
    await db.commit()
    svc.enqueue_support_delivery()
    include_internal = svc.support_can(claims, "internal_note")
    return env(
        await svc.ticket_detail(db, ticket, desk=True, include_internal=include_internal),
        "Reply sent",
    )


@router.post("/desk/tickets/{ticket_id}/notes")
async def desk_ticket_note(
    ticket_id: str,
    body: ReplyBody,
    request: Request,
    claims: dict = Depends(require_support("internal_note")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    await svc.add_internal_note(db, claims, actor_from(request, claims), ticket, body.body)
    await db.commit()
    return env(
        await svc.ticket_detail(db, ticket, desk=True, include_internal=True),
        "Internal note saved",
    )


@router.patch("/desk/tickets/{ticket_id}")
async def desk_ticket_update(
    ticket_id: str,
    body: TicketUpdate,
    request: Request,
    claims: dict = Depends(require_support("manage")),
    db: AsyncSession = Depends(get_db),
):
    if body.assignee_set and not svc.support_can(claims, "assign"):
        raise HTTPException(status_code=403, detail="Missing permission: support:assign")
    ticket = await svc.require_ticket(db, claims, ticket_id)
    await svc.update_ticket(
        db,
        actor_from(request, claims),
        ticket,
        status=body.status,
        priority=body.priority,
        category=body.category,
        assignee_user_id=body.assignee_user_id,
        assignee_set=body.assignee_set,
    )
    await db.commit()
    svc.enqueue_support_delivery()
    include_internal = svc.support_can(claims, "internal_note")
    return env(await svc.ticket_detail(db, ticket, desk=True, include_internal=include_internal), "Ticket updated")


@router.post("/desk/tickets/{ticket_id}/close")
async def desk_ticket_close(
    ticket_id: str,
    request: Request,
    claims: dict = Depends(require_support("close")),
    db: AsyncSession = Depends(get_db),
):
    if not svc.support_can(claims, "view_all"):
        raise HTTPException(status_code=403, detail="Missing permission: support:view_all")
    ticket = await svc.require_ticket(db, claims, ticket_id)
    await svc.apply_status(db, actor_from(request, claims), ticket, "closed")
    await db.commit()
    svc.enqueue_support_delivery()
    include_internal = svc.support_can(claims, "internal_note")
    return env(
        await svc.ticket_detail(db, ticket, desk=True, include_internal=include_internal),
        "Ticket closed",
    )


@router.post("/desk/tickets/{ticket_id}/reopen")
async def desk_ticket_reopen(
    ticket_id: str,
    request: Request,
    claims: dict = Depends(require_support("manage")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await svc.require_ticket(db, claims, ticket_id)
    if ticket.status not in {"resolved", "closed"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATUS_TRANSITION", "message": "Only a resolved or closed ticket can be reopened"},
        )
    await svc.apply_status(
        db,
        actor_from(request, claims),
        ticket,
        "in_progress",
        action="support_ticket_reopened",
    )
    await db.commit()
    svc.enqueue_support_delivery()
    include_internal = svc.support_can(claims, "internal_note")
    return env(
        await svc.ticket_detail(db, ticket, desk=True, include_internal=include_internal),
        "Ticket reopened",
    )


@router.get("/desk/deliveries")
async def desk_deliveries(
    claims: dict = Depends(require_support("view_all")),
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    _ = claims
    return env(await svc.list_deliveries(db, status=status, limit=limit, offset=offset))


@router.post("/desk/deliveries/{delivery_id}/retry")
async def desk_delivery_retry(
    delivery_id: str,
    request: Request,
    claims: dict = Depends(require_support("manage")),
    db: AsyncSession = Depends(get_db),
):
    result = await svc.retry_delivery(db, actor_from(request, claims), delivery_id)
    await db.commit()
    return env(result, "Delivery checked")


@router.get("/desk/recipients")
async def desk_recipients(
    claims: dict = Depends(require_support("notification_manage")),
    db: AsyncSession = Depends(get_db),
):
    _ = claims
    data = await svc.list_recipients(db)
    await db.commit()
    return env(data)


@router.post("/desk/recipients")
async def desk_recipient_add(
    body: RecipientBody,
    request: Request,
    claims: dict = Depends(require_support("notification_manage")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc.add_recipient(db, actor_from(request, claims), body.email)
    await db.commit()
    return env({"id": row.id, "email": row.email, "is_active": row.is_active}, "Recipient added")


@router.patch("/desk/recipients/{recipient_id}")
async def desk_recipient_update(
    recipient_id: str,
    body: RecipientUpdate,
    request: Request,
    claims: dict = Depends(require_support("notification_manage")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc.update_recipient(
        db,
        actor_from(request, claims),
        recipient_id,
        email=body.email,
        is_active=body.is_active,
    )
    await db.commit()
    return env({"id": row.id, "email": row.email, "is_active": row.is_active}, "Recipient updated")


@router.delete("/desk/recipients/{recipient_id}")
async def desk_recipient_remove(
    recipient_id: str,
    request: Request,
    claims: dict = Depends(require_support("notification_manage")),
    db: AsyncSession = Depends(get_db),
):
    await svc.remove_recipient(db, actor_from(request, claims), recipient_id)
    await db.commit()
    return env({"id": recipient_id}, "Recipient removed")


@router.post("/desk/recipients/{recipient_id}/test-email")
async def desk_recipient_test(
    recipient_id: str,
    request: Request,
    claims: dict = Depends(require_support("notification_manage")),
    db: AsyncSession = Depends(get_db),
):
    result = await svc.send_recipient_test(db, actor_from(request, claims), recipient_id)
    await db.commit()
    return env(result, "Test email processed")
