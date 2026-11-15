"""What a bakery knows about an item beyond its price and stock.

- Shelf life: a bake gets a best-before date (baked day + shelf life). What is on the shelf is
  taken to be the newest bakes (oldest sell first), so each bake's share of today's stock shows
  what is fresh, day-old, last day, or past its date.
- Day-old price: a percent off for bread baked before today, set by a manager. Any cashier may
  use it, but only for as much day-old stock as there is.
- Allergens and label text: the item's own allergens plus those of every ingredient in its
  recipe, and an ingredient list in descending order of weight, for the label.
- Units: an ingredient is kept in a stock unit (kg, g, l, ml, each) and may be bought in a bigger
  unit (a 50 kg bag). Recipes may be written in grams for a kilo ingredient.
- Shelf level: how many to have on the shelf every day, so "what to bake" covers walk-in sales,
  not only orders.
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative

# The fourteen allergens food law asks bakers to declare (Codex / EU list, used by Ghana FDA labels).
ALLERGENS = {
    "gluten": "Cereals containing gluten (wheat, barley, rye, oats)",
    "eggs": "Eggs",
    "milk": "Milk",
    "nuts": "Tree nuts",
    "peanuts": "Peanuts",
    "soya": "Soya",
    "sesame": "Sesame",
    "fish": "Fish",
    "crustaceans": "Crustaceans",
    "molluscs": "Molluscs",
    "celery": "Celery",
    "mustard": "Mustard",
    "sulphites": "Sulphites",
    "lupin": "Lupin",
}
# Unit -> (kind, size in the smallest unit of that kind).
UNITS = {
    "kg": ("mass", 1000.0),
    "g": ("mass", 1.0),
    "l": ("volume", 1000.0),
    "ml": ("volume", 1.0),
    "each": ("count", 1.0),
}


def _qty(value) -> float:
    return money_json(round(float(value or 0), 3))


def convert(quantity: float, from_unit: str | None, to_unit: str | None) -> float:
    """Grams to kilos and the like. Units of different kinds never convert."""
    src = (from_unit or to_unit or "each").lower()
    dst = (to_unit or "each").lower()
    if src == dst:
        return float(quantity)
    if src not in UNITS or dst not in UNITS or UNITS[src][0] != UNITS[dst][0]:
        raise HTTPException(status_code=422, detail=f"{src} cannot be turned into {dst}")
    return float(quantity) * UNITS[src][1] / UNITS[dst][1]


async def settings_map(db: AsyncSession, tenant_id: str, product_ids: list[str] | None = None) -> dict[str, m.BakeryItemSettings]:
    stmt = select(m.BakeryItemSettings).where(m.BakeryItemSettings.tenant_id == tenant_id)
    if product_ids is not None:
        if not product_ids:
            return {}
        stmt = stmt.where(m.BakeryItemSettings.product_id.in_(product_ids))
    return {row.product_id: row for row in (await db.execute(stmt)).scalars().all()}


async def settings_for(db: AsyncSession, tenant_id: str, product_id: str) -> m.BakeryItemSettings | None:
    return (await settings_map(db, tenant_id, [product_id])).get(product_id)


def stock_unit(row: m.BakeryItemSettings | None) -> str:
    return (row.stock_unit if row and row.stock_unit else "each")


def present(row: m.BakeryItemSettings | None) -> dict:
    return {
        "shelf_life_days": row.shelf_life_days if row else None,
        "day_old_discount_pct": money_json(row.day_old_discount_pct) if row and row.day_old_discount_pct is not None else None,
        "allergens": list(row.allergens or []) if row else [],
        "ingredients_text": row.ingredients_text if row else None,
        "net_weight": row.net_weight if row else None,
        "storage_note": row.storage_note if row else None,
        "stock_unit": stock_unit(row),
        "purchase_unit": row.purchase_unit if row else None,
        "units_per_purchase": _qty(row.units_per_purchase) if row and row.units_per_purchase else None,
        "par_level": _qty(row.par_level) if row and row.par_level else None,
    }


async def save(db: AsyncSession, tenant_id: str, product_id: str, payload, *, user_id) -> m.BakeryItemSettings:
    product = await db.get(m.Product, product_id)
    if product is None or product.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Item not found")
    data = payload.model_dump(exclude_unset=True)
    row = await settings_for(db, tenant_id, product_id)
    if row is None:
        row = m.BakeryItemSettings(tenant_id=tenant_id, product_id=product_id)
        db.add(row)
    if "allergens" in data:
        keys = [str(a).strip().lower() for a in (data["allergens"] or [])]
        unknown = [k for k in keys if k not in ALLERGENS]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Not an allergen on the list: {', '.join(unknown)}")
        row.allergens = sorted(set(keys))
    if "stock_unit" in data:
        unit = (data["stock_unit"] or "each").lower()
        if unit not in UNITS:
            raise HTTPException(status_code=422, detail="Choose kg, g, l, ml or each")
        if row.stock_unit and row.stock_unit != unit and float(product.stock_qty or 0) != 0:
            raise HTTPException(
                status_code=409,
                detail="This item already has stock in another unit. Count it to zero or add a new item.",
            )
        row.stock_unit = unit
    for key in ("shelf_life_days", "day_old_discount_pct", "units_per_purchase", "par_level"):
        if key in data:
            setattr(row, key, data[key])
    for key, size in (("ingredients_text", 2000), ("net_weight", 40), ("storage_note", 200), ("purchase_unit", 30)):
        if key in data:
            setattr(row, key, optional_honest_narrative(data[key], label=key.replace("_", " "), max_length=size))
    if row.purchase_unit and not row.units_per_purchase:
        raise HTTPException(status_code=422, detail="Say how many stock units are in one purchase unit")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


# --- Shelf life ----------------------------------------------------------------------------


async def shelf(db: AsyncSession, tenant_id: str, *, today: date, local) -> list[dict]:
    """Each bake still on the shelf, newest first, with how much of today's stock is from it."""
    from app.bakery import _money  # noqa: F401 - keeps one rounding rule

    batches = (
        await db.execute(
            select(m.BakeryBatch, m.Product)
            .join(m.Product, m.Product.id == m.BakeryBatch.product_id)
            .where(m.BakeryBatch.tenant_id == tenant_id, m.Product.stock_qty > 0)
            .order_by(m.BakeryBatch.created_at.desc())
        )
    ).all()
    settings = await settings_map(db, tenant_id, list({p.id for _, p in batches}))
    left: dict[str, float] = {}
    out: list[dict] = []
    for batch, product in batches:
        remaining = left.setdefault(product.id, float(product.stock_qty or 0))
        if remaining <= 0.0005:
            continue
        here = min(remaining, float(batch.made_qty or 0))
        left[product.id] = remaining - here
        baked_on = local(batch.created_at).date()
        best = batch.best_before
        if best is not None and best < today:
            state = "expired"
        elif best is not None and best == today:
            state = "last_day"
        elif baked_on < today:
            state = "day_old"
        else:
            state = "fresh"
        conf = settings.get(product.id)
        out.append(
            {
                "product_id": product.id,
                "name": product.name,
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "baked_on": baked_on.isoformat(),
                "best_before": best.isoformat() if best else None,
                "quantity": _qty(here),
                "state": state,
                "day_old_discount_pct": money_json(conf.day_old_discount_pct)
                if conf and conf.day_old_discount_pct is not None
                else None,
            }
        )
    return out


async def day_old_on_hand(db: AsyncSession, tenant_id: str, product_id: str, *, today: date, local) -> float:
    """How many of this item on the shelf were baked before today and are still in date."""
    rows = await shelf(db, tenant_id, today=today, local=local)
    return _qty(sum(r["quantity"] for r in rows if r["product_id"] == product_id and r["state"] in ("day_old", "last_day")))


# --- Labels --------------------------------------------------------------------------------


async def label_facts(db: AsyncSession, tenant_id: str, product: m.Product) -> dict:
    """Ingredients by weight, largest first, and allergens from the item and every ingredient."""
    own = await settings_for(db, tenant_id, product.id)
    recipe = (
        await db.execute(
            select(m.BakeryRecipe).where(m.BakeryRecipe.tenant_id == tenant_id, m.BakeryRecipe.product_id == product.id)
        )
    ).scalars().first()
    allergens: set[str] = set(own.allergens or []) if own else set()
    if recipe is not None:
        lines = (
            await db.execute(
                select(m.BakeryRecipeLine, m.Product)
                .join(m.Product, m.Product.id == m.BakeryRecipeLine.ingredient_id)
                .where(m.BakeryRecipeLine.recipe_id == recipe.id)
            )
        ).all()
        inner = await settings_map(db, tenant_id, [p.id for _, p in lines])
        weighed = []
        for line, ingredient in lines:
            conf = inner.get(ingredient.id)
            unit = stock_unit(conf)
            try:
                base = convert(float(line.quantity), unit, "g" if UNITS.get(unit, ("count",))[0] == "mass" else (
                    "ml" if UNITS.get(unit, ("count",))[0] == "volume" else unit))
            except HTTPException:
                base = float(line.quantity)
            has = bool(conf and conf.allergens)
            weighed.append((base, ingredient.name, has))
            allergens |= set(conf.allergens or []) if conf else set()
        parts = [{"name": name, "allergen": has} for _, name, has in sorted(weighed, key=lambda x: -x[0])]
    else:
        parts = []
    if own and own.ingredients_text:
        parts = [{"name": own.ingredients_text, "allergen": False}]
    return {
        "ingredients": ", ".join(p["name"] for p in parts),
        "ingredient_parts": parts,
        "allergens": sorted(allergens),
        "allergen_names": [ALLERGENS[a] for a in sorted(allergens) if a in ALLERGENS],
        "net_weight": own.net_weight if own else None,
        "storage_note": own.storage_note if own else None,
        "shelf_life_days": own.shelf_life_days if own else None,
    }


async def label_html(
    db: AsyncSession, tenant_id: str, product_id: str, *, batch_id: str | None, copies: int, today: date
) -> str:
    from app.bakery import _money

    product = await db.get(m.Product, product_id)
    if product is None or product.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Item not found")
    facts = await label_facts(db, tenant_id, product)
    batch = None
    if batch_id:
        batch = await db.get(m.BakeryBatch, batch_id)
        if batch is None or batch.tenant_id != tenant_id or batch.product_id != product.id:
            raise HTTPException(status_code=404, detail="Bake not found")
    company = await db.get(m.Tenant, tenant_id)
    best = batch.best_before if batch and batch.best_before else (
        today + timedelta(days=int(facts["shelf_life_days"])) if facts["shelf_life_days"] else None
    )
    # Ingredients that carry an allergen are in bold in the list, as labelling rules ask.
    marked = [
        f"<b>{html.escape(p['name'])}</b>" if p["allergen"] else html.escape(p["name"]) for p in facts["ingredient_parts"]
    ]
    allergen_line = ", ".join(html.escape(a) for a in facts["allergen_names"]) or "None declared"
    one = (
        '<div class="lbl">'
        f'<div class="nm">{html.escape(product.name)}</div>'
        f'<div><b>Ingredients:</b> {", ".join(marked) or "Not set"}</div>'
        f'<div><b>Allergens:</b> {allergen_line}</div>'
        + (f'<div>Net weight: {html.escape(facts["net_weight"])}</div>' if facts["net_weight"] else "")
        + (f'<div>Best before: <b>{best.strftime("%d %b %Y")}</b></div>' if best else "")
        + (f'<div>Batch: {html.escape(batch.batch_number)}</div>' if batch else "")
        + (f'<div>{html.escape(facts["storage_note"])}</div>' if facts["storage_note"] else "")
        + f'<div class="pr">{_money(product.selling_price):.2f}</div>'
        f'<div class="co">{html.escape(getattr(company, "company_name", "") or "")}</div>'
        "</div>"
    )
    style = (
        "body{font-family:Arial,sans-serif;margin:0}"
        ".lbl{width:58mm;padding:3mm;border:1px dashed #999;margin:2mm;display:inline-block;vertical-align:top;font-size:9pt;line-height:1.3}"
        ".nm{font-size:12pt;font-weight:bold;margin-bottom:1mm}.pr{font-size:12pt;font-weight:bold;margin-top:1mm}"
        ".co{font-size:8pt;color:#444}@media print{.lbl{border:none}}"
    )
    copies = max(1, min(int(copies or 1), 60))
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(product.name)} label</title>"
        f"<style>{style}</style></head><body>{one * copies}<script>window.onload=()=>window.print()</script></body></html>"
    )
