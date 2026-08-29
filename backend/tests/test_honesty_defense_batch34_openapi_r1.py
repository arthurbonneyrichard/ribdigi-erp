"""OpenAPI honesty tips #1779–#1801: residual money_json + FE aria."""

from __future__ import annotations

import inspect
from pathlib import Path

from app.honesty import money_json
from app import product_import as product_import_mod
from app import ai as ai_mod
from app import ai_documents as ai_documents_mod
from app import ai_inventory as ai_inventory_mod
from app import ai_sales as ai_sales_mod
from app import purchase_suggestions as purchase_suggestions_mod
from app import api as api_mod

ROOT = Path(__file__).resolve().parents[2]


def test_honesty_batch34_docs_and_agents():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Product CSV validate cost_price money_json Decimal pilot OpenAPI",
        "Product CSV validate selling_price money_json Decimal pilot OpenAPI",
        "Product CSV validate stock_qty money_json Decimal pilot OpenAPI",
        "Product CSV validate reorder_level money_json Decimal pilot OpenAPI",
        "Product CSV validate dimensions money_json Decimal pilot OpenAPI",
        "AI sales spike pct money_json Decimal pilot OpenAPI",
        "AI restock days_to_stockout money_json Decimal pilot OpenAPI",
        "AI restock seasonality ratio money_json Decimal pilot OpenAPI",
        "AI document OCR confidence money_json Decimal pilot OpenAPI",
        "AI inventory lead days money_json Decimal pilot OpenAPI",
        "AI inventory cover days money_json Decimal pilot OpenAPI",
        "AI inventory velocity lookback money_json Decimal pilot OpenAPI",
        "AI inventory recent velocity denom money_json Decimal pilot OpenAPI",
        "AI inventory prior velocity denom money_json Decimal pilot OpenAPI",
        "AI sales RFM frequency money_json Decimal pilot OpenAPI",
        "AI prediction confidence money_json Decimal pilot OpenAPI",
        "AI prediction min_confidence money_json Decimal pilot OpenAPI",
        "Party serialize latitude money_json Decimal pilot OpenAPI",
        "Party serialize longitude money_json Decimal pilot OpenAPI",
        "Party normalize latitude money_json Decimal pilot OpenAPI",
        "Party normalize longitude money_json Decimal pilot OpenAPI",
        "API product audit float _jsonable money_json Decimal pilot OpenAPI",
        "Party contact email aria OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    standards = docs.split("## 1. API Standards")[1].split("## 2.")[0]
    assert "product CSV validate `_parse_float`" in standards
    assert "party serialize/normalize latitude/longitude" in standards

    contacts = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Party contact email"' in contacts


def test_money_json_wired_batch34():
    assert money_json("12.50") == 12.5

    parse_src = inspect.getsource(product_import_mod._parse_float)
    assert "return money_json(default)" in parse_src
    assert "return money_json(float(text))" in parse_src

    spike_src = inspect.getsource(ai_mod._sales_spike_drop_notes)
    assert "pct_f = money_json(pct)" in spike_src

    compose_src = inspect.getsource(ai_mod.compose_insights)
    assert "dts_f = money_json(dts) if dts is not None else None" in compose_src
    assert "ratio_f = money_json(ratio) if ratio is not None else None" in compose_src

    ai_docs_src = Path(ai_documents_mod.__file__).read_text(encoding="utf-8")
    assert 'confidence = money_json(ocr.get("confidence") or 0)' in ai_docs_src

    inv_src = Path(ai_inventory_mod.__file__).read_text(encoding="utf-8")
    assert "lead = money_json(default_lead_days())" in inv_src
    assert "cover = money_json(cover_days())" in inv_src
    assert "lb_f = money_json(lb)" in inv_src
    assert "half_f = money_json(half)" in inv_src
    assert "prior_span = money_json(max(1, lb - half))" in inv_src
    assert "velocity = sold / lb_f if lb_f else 0.0" in inv_src
    assert "recent_v = money_json(sold_recent.get(pid, 0)) / half_f" in inv_src
    assert "prior_v = money_json(sold_prior.get(pid, 0)) / prior_span" in inv_src

    sales_src = Path(ai_sales_mod.__file__).read_text(encoding="utf-8")
    assert 'freq = {cid: money_json(row["frequency"]) for cid, row in cust.items()}' in sales_src

    pred_src = inspect.getsource(purchase_suggestions_mod.create_requests_from_predictions)
    assert 'conf = money_json(raw.get("confidence") or 0)' in pred_src
    assert "conf < money_json(min_confidence or 0)" in pred_src

    party_src = inspect.getsource(api_mod._serialize_party)
    assert '"latitude": money_json(lat) if lat is not None else None' in party_src
    assert '"longitude": money_json(lng) if lng is not None else None' in party_src

    api_src = Path(api_mod.__file__).read_text(encoding="utf-8")
    assert "val = money_json(data[coord])" in api_src
    assert "return money_json(round(value, 4))" in api_src
