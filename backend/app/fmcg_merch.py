"""FMCG merchandising: must-stock list, shelf audits, competitor prices and the shelf report.

A shelf audit is a checklist taken at an outlet. Every product on the company's must-stock list has
to be answered, so an audit can never quietly skip the hard lines. The score is the share of
must-stock products that are on the shelf with at least their minimum number of facings. A rep can
only audit outlets in their territory; managers can audit any.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import fmcg_field as field_svc
from app import fmcg_orders as orders
from app import fmcg_quality as quality_svc
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

PHOTO_MAX = 800_000


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_shelf_audit", entity_id=entity_id, details=details,
    )


async def _products(db, tenant_id: str, ids: list[str]) -> dict[str, m.Product]:
    rows = (await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.id.in_(ids)))).scalars().all()
    found = {p.id: p for p in rows}
    if len(found) != len(set(ids)):
        raise HTTPException(status_code=404, detail="One of those products was not found")
    return found


# ---------------------------------------------------------------- must-stock

async def get_must_stock(db, *, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.FmcgMustStock, m.Product).join(m.Product, m.Product.id == m.FmcgMustStock.product_id)
            .where(m.FmcgMustStock.tenant_id == tenant_id).order_by(m.Product.name)
        )
    ).all()
    return [{"product_id": p.id, "product": p.name, "min_facings": ms.min_facings} for ms, p in rows]


async def set_must_stock(db, *, tenant_id: str, items: list[dict], user_id) -> list[dict]:
    ids = [i["product_id"] for i in items]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Each product can be on the list once")
    if ids:
        await _products(db, tenant_id, ids)
    existing = {
        r.product_id: r for r in (await db.execute(select(m.FmcgMustStock).where(m.FmcgMustStock.tenant_id == tenant_id))).scalars().all()
    }
    for pid, row in existing.items():
        if pid not in ids:
            await db.delete(row)
    for item in items:
        row = existing.get(item["product_id"])
        if row is None:
            db.add(m.FmcgMustStock(tenant_id=tenant_id, product_id=item["product_id"], min_facings=item["min_facings"]))
        else:
            row.min_facings = item["min_facings"]
    await _audit(db, tenant_id, user_id, "fmcg_must_stock_saved", tenant_id, {"products": len(items)})
    await db.flush()
    return await get_must_stock(db, tenant_id=tenant_id)


# ---------------------------------------------------------------- audits

async def create_audit(
    db, *, tenant_id: str, user_id, may_audit_any: bool, outlet_id: str, visit_id: str | None, display_ok: bool | None,
    notes: str | None, photo: str | None, lines: list[dict], at: datetime | None = None,
) -> dict:
    outlet = await orders._outlet(db, tenant_id, outlet_id)
    if not may_audit_any:
        assignment = (
            await db.execute(
                select(m.FmcgCustomerAssignment).where(
                    m.FmcgCustomerAssignment.tenant_id == tenant_id, m.FmcgCustomerAssignment.customer_id == outlet.id
                )
            )
        ).scalars().first()
        mine = await field_svc.my_route_ids(db, tenant_id, user_id)
        if (assignment.route_id if assignment else None) not in mine:
            raise HTTPException(status_code=403, detail={"code": "OUTSIDE_TERRITORY", "message": "That outlet is not in your territory."})
    if visit_id:
        visit = (await db.execute(select(m.FmcgVisit).where(m.FmcgVisit.id == visit_id, m.FmcgVisit.tenant_id == tenant_id))).scalar_one_or_none()
        if visit is None:
            raise HTTPException(status_code=404, detail="Visit not found")
        if visit.outlet_id != outlet.id or (not may_audit_any and visit.user_id != user_id):
            raise HTTPException(status_code=422, detail="That visit is not yours, or not at this outlet")
    ids = [l["product_id"] for l in lines]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Each product can be answered once")
    products = await _products(db, tenant_id, ids) if ids else {}
    must = {r["product_id"]: r for r in await get_must_stock(db, tenant_id=tenant_id)}
    missing = [r["product"] for pid, r in must.items() if pid not in ids]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"code": "MUST_STOCK_INCOMPLETE", "message": f"Answer every must-stock product. Missing: {', '.join(missing[:8])}"},
        )
    for l in lines:
        if l["present"] and l["facings"] < 1:
            raise HTTPException(status_code=422, detail="A product on the shelf needs at least 1 facing")
        if not l["present"] and l["facings"] > 0:
            raise HTTPException(status_code=422, detail="A product that is not on the shelf has no facings")
    pic = quality_svc._image(photo, limit=PHOTO_MAX, label="photo")
    required = available = compliant = 0
    for l in lines:
        spec = must.get(l["product_id"])
        if spec:
            required += 1
            if l["present"]:
                available += 1
                if l["facings"] >= spec["min_facings"]:
                    compliant += 1
    row = m.FmcgShelfAudit(
        tenant_id=tenant_id, outlet_id=outlet.id, visit_id=visit_id, auditor_id=user_id, display_ok=display_ok,
        required=required, available=available, compliant=compliant,
        score_pct=round(100 * compliant / required, 1) if required else None,
        notes=optional_honest_narrative(notes, label="notes", max_length=500), photo=pic,
        **({"audited_at": at} if at else {}),
    )
    db.add(row)
    await db.flush()
    for l in lines:
        spec = must.get(l["product_id"])
        db.add(
            m.FmcgShelfAuditLine(
                tenant_id=tenant_id, audit_id=row.id, product_id=l["product_id"], present=l["present"], facings=l["facings"],
                shelf_price=l.get("shelf_price"), must_stock=bool(spec), min_facings=spec["min_facings"] if spec else 0,
            )
        )
    await _audit(db, tenant_id, user_id, "fmcg_shelf_audit", row.id, {"outlet_id": outlet.id, "score_pct": float(row.score_pct) if row.score_pct is not None else None})
    await db.flush()
    return await _present(db, row, products=products)


async def _present(db, row: m.FmcgShelfAudit, *, products: dict | None = None, lines: bool = True, photo: bool = False) -> dict:
    outlet = await db.get(m.Party, row.outlet_id)
    auditor = await db.get(m.User, row.auditor_id) if row.auditor_id else None
    data = {
        "id": row.id, "outlet_id": row.outlet_id, "outlet": outlet.name if outlet else None, "visit_id": row.visit_id,
        "auditor": auditor.full_name if auditor else None, "audited_at": row.audited_at.isoformat(timespec="seconds"),
        "display_ok": row.display_ok, "required": row.required, "available": row.available, "compliant": row.compliant,
        "score_pct": float(row.score_pct) if row.score_pct is not None else None, "notes": row.notes, "has_photo": bool(row.photo),
    }
    if photo:
        data["photo"] = row.photo
    if lines:
        rows = (
            await db.execute(
                select(m.FmcgShelfAuditLine, m.Product).join(m.Product, m.Product.id == m.FmcgShelfAuditLine.product_id)
                .where(m.FmcgShelfAuditLine.audit_id == row.id).order_by(m.Product.name)
            )
        ).all()
        data["lines"] = [
            {"product_id": p.id, "product": p.name, "present": l.present, "facings": l.facings, "must_stock": l.must_stock,
             "min_facings": l.min_facings, "shelf_price": money_json(l.shelf_price) if l.shelf_price is not None else None,
             "our_price": money_json(p.selling_price)}
            for l, p in rows
        ]
    return data


async def list_audits(db, *, tenant_id: str, user_id: str | None, outlet_id: str | None, days: int) -> list[dict]:
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    stmt = select(m.FmcgShelfAudit).where(m.FmcgShelfAudit.tenant_id == tenant_id, m.FmcgShelfAudit.audited_at >= since)
    if user_id:
        stmt = stmt.where(m.FmcgShelfAudit.auditor_id == user_id)
    if outlet_id:
        stmt = stmt.where(m.FmcgShelfAudit.outlet_id == outlet_id)
    rows = (await db.execute(stmt.order_by(m.FmcgShelfAudit.audited_at.desc()).limit(200))).scalars().all()
    return [await _present(db, r, lines=False) for r in rows]


async def get_audit(db, *, tenant_id: str, audit_id: str, user_id: str | None) -> dict:
    row = (await db.execute(select(m.FmcgShelfAudit).where(m.FmcgShelfAudit.id == audit_id, m.FmcgShelfAudit.tenant_id == tenant_id))).scalar_one_or_none()
    if row is None or (user_id and row.auditor_id != user_id):
        raise HTTPException(status_code=404, detail="Audit not found")
    return await _present(db, row, photo=True)


# ---------------------------------------------------------------- competitor prices

async def add_competitor_price(
    db, *, tenant_id: str, user_id, outlet_id: str | None, product_id: str, brand: str, competitor_product: str, price: float, note: str | None,
    at: datetime | None = None,
) -> dict:
    await _products(db, tenant_id, [product_id])
    if outlet_id:
        await orders._outlet(db, tenant_id, outlet_id)
    if price <= 0:
        raise HTTPException(status_code=422, detail="Enter the shelf price")
    row = m.FmcgCompetitorPrice(
        tenant_id=tenant_id, outlet_id=outlet_id, product_id=product_id,
        competitor_brand=require_honest_narrative(brand, label="competitor brand", max_length=120),
        competitor_product=require_honest_narrative(competitor_product, label="competitor product", max_length=160),
        price=price, note=optional_honest_narrative(note, label="note", max_length=300), observed_by=user_id,
        **({"observed_at": at} if at else {}),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_competitor_price", row.id, {"product_id": product_id, "price": price})
    return _price_row(row)


def _price_row(r: m.FmcgCompetitorPrice) -> dict:
    return {"id": r.id, "outlet_id": r.outlet_id, "product_id": r.product_id, "brand": r.competitor_brand, "competitor_product": r.competitor_product,
            "price": money_json(r.price), "note": r.note, "observed_at": r.observed_at.isoformat(timespec="seconds")}


async def list_competitor_prices(db, *, tenant_id: str, days: int) -> list[dict]:
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    rows = (
        await db.execute(
            select(m.FmcgCompetitorPrice).where(m.FmcgCompetitorPrice.tenant_id == tenant_id, m.FmcgCompetitorPrice.observed_at >= since)
            .order_by(m.FmcgCompetitorPrice.observed_at.desc()).limit(300)
        )
    ).scalars().all()
    return [_price_row(r) for r in rows]


# ---------------------------------------------------------------- report

async def report(db, *, tenant_id: str, start: date, end: date) -> dict:
    begin, finish = datetime.combine(start, time.min), datetime.combine(end, time.max)
    audits = (
        await db.execute(
            select(m.FmcgShelfAudit).where(m.FmcgShelfAudit.tenant_id == tenant_id, m.FmcgShelfAudit.audited_at >= begin, m.FmcgShelfAudit.audited_at <= finish)
            .order_by(m.FmcgShelfAudit.audited_at)
        )
    ).scalars().all()
    latest: dict[str, m.FmcgShelfAudit] = {}
    for a in audits:
        latest[a.outlet_id] = a
    outlet_names = {p.id: p.name for p in (await db.execute(select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer"))).scalars().all()}
    active = (
        await db.execute(select(func.count()).select_from(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.status == "active"))
    ).scalar_one()
    users = {u.id: u.full_name for u in (await db.execute(select(m.User).where(m.User.tenant_id == tenant_id))).scalars().all()}
    outlets = [
        {"outlet_id": oid, "outlet": outlet_names.get(oid, "?"), "audited_at": a.audited_at.date().isoformat(), "required": a.required,
         "available": a.available, "compliant": a.compliant, "score_pct": float(a.score_pct) if a.score_pct is not None else None,
         "display_ok": a.display_ok}
        for oid, a in sorted(latest.items(), key=lambda t: (t[1].score_pct if t[1].score_pct is not None else 101))
    ]
    reps: dict = defaultdict(lambda: {"audits": 0, "scores": []})
    for a in audits:
        r = reps[a.auditor_id]
        r["audits"] += 1
        if a.score_pct is not None:
            r["scores"].append(float(a.score_pct))
    audit_ids = [a.id for a in audits]
    products = []
    shelf_prices: dict[str, list[float]] = defaultdict(list)
    if audit_ids:
        line_rows = (
            await db.execute(
                select(m.FmcgShelfAuditLine, m.Product).join(m.Product, m.Product.id == m.FmcgShelfAuditLine.product_id)
                .where(m.FmcgShelfAuditLine.audit_id.in_(audit_ids))
            )
        ).all()
        per: dict = defaultdict(lambda: {"name": "", "audits": 0, "present": 0, "must": False})
        for l, p in line_rows:
            g = per[p.id]
            g["name"], g["must"] = p.name, g["must"] or l.must_stock
            g["audits"] += 1
            g["present"] += 1 if l.present else 0
            if l.shelf_price is not None:
                shelf_prices[p.id].append(float(l.shelf_price))
        products = sorted(
            ({"product_id": pid, "product": g["name"], "must_stock": g["must"], "audited_at_outlets": g["audits"], "out_of_stock_at": g["audits"] - g["present"],
              "availability_pct": round(100 * g["present"] / g["audits"], 1)} for pid, g in per.items()),
            key=lambda r: r["availability_pct"],
        )
    prices = []
    comp = (
        await db.execute(
            select(m.FmcgCompetitorPrice, m.Product).join(m.Product, m.Product.id == m.FmcgCompetitorPrice.product_id)
            .where(m.FmcgCompetitorPrice.tenant_id == tenant_id, m.FmcgCompetitorPrice.observed_at >= begin, m.FmcgCompetitorPrice.observed_at <= finish)
        )
    ).all()
    by_product: dict = defaultdict(lambda: {"product": None, "ours": 0.0, "seen": []})
    for c, p in comp:
        g = by_product[p.id]
        g["product"], g["ours"] = p.name, float(p.selling_price or 0)
        g["seen"].append(float(c.price))
    for pid, g in by_product.items():
        avg = sum(g["seen"]) / len(g["seen"])
        shelf = shelf_prices.get(pid)
        prices.append(
            {"product_id": pid, "product": g["product"], "our_list_price": money_json(g["ours"]), "our_shelf_price_avg": round(sum(shelf) / len(shelf), 2) if shelf else None,
             "competitor_avg": round(avg, 2), "competitor_low": min(g["seen"]), "competitor_high": max(g["seen"]), "sightings": len(g["seen"]),
             "price_index": round(100 * g["ours"] / avg, 1) if avg > 0 else None}
        )
    scores = [o["score_pct"] for o in outlets if o["score_pct"] is not None]
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": {
            "audits": len(audits), "outlets_audited": len(latest), "active_outlets": int(active or 0),
            "coverage_pct": round(100 * len(latest) / active, 1) if active else None,
            "average_score_pct": round(sum(scores) / len(scores), 1) if scores else None,
        },
        "outlets": outlets,
        "products": products,
        "reps": sorted(
            ({"auditor": users.get(uid, "?"), "audits": r["audits"], "average_score_pct": round(sum(r["scores"]) / len(r["scores"]), 1) if r["scores"] else None}
             for uid, r in reps.items()), key=lambda r: -r["audits"],
        ),
        "prices": sorted(prices, key=lambda r: -(r["price_index"] or 0)),
        "note": "Price index: our list price as a percentage of the competitor average. Over 100 means we are dearer.",
    }
