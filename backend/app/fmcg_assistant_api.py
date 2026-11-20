"""FMCG assistant routes. Read-only; managers and admins only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_assistant as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/fmcg/assistant", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class AskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=3, max_length=300)]


@router.get("/examples")
async def examples(claims=Depends(require_permission("fmcg", "read"))):
    orders.job(claims, "assistant")
    return _env(svc.EXAMPLES)


@router.post("/ask")
async def ask(payload: AskBody, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "assistant")
    return _env(await svc.answer(db, tenant_id=claims["tenant_id"], question=payload.question))
