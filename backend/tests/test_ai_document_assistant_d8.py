"""Rule-based AI Document Assistant (BR-21.8)."""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfWriter

from app import ai_documents as ai_doc
from app import expense_ocr as ocr_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_name_similarity_and_infer_type():
    assert ai_doc.name_similarity("ACME Supplies Ltd", "ACME Supplies") >= 0.9
    assert ai_doc.name_similarity("Foo", "Bar") < 0.45
    assert ai_doc.infer_document_type("Purchase Order PO-1001", "auto") == "purchase_order"
    assert ai_doc.infer_document_type("Tax Invoice INV-1", "auto") == "invoice"
    assert ai_doc.infer_document_type("Merchant receipt", "auto") == "receipt"
    assert ai_doc.infer_document_type("x", "receipt") == "receipt"


def test_build_discrepancies_amount_mismatch():
    flags = ai_doc.build_discrepancies(
        fields={"amount": 100.0, "expense_date": "2026-01-01", "payee": "X"},
        confidence=0.8,
        expected_amount=50.0,
        party_matches=[{"party_id": "1"}],
        po_matches=[],
        duplicate_refs=[],
        document_type="invoice",
    )
    codes = {f["code"] for f in flags}
    assert "amount_mismatch" in codes


@pytest.mark.asyncio
async def test_documents_analyze_match_and_discrepancy(client, db_session, monkeypatch):
    ac, seed = client
    tid = seed["t1"].id
    supplier = m.Party(
        tenant_id=tid,
        kind="supplier",
        name="ACME Supplies Ltd",
        credit_limit=0,
    )
    db_session.add(supplier)
    await db_session.flush()
    po = m.PurchaseOrder(
        tenant_id=tid,
        po_number="PO-ACME-99",
        supplier_id=supplier.id,
        status="sent",
        total_amount=250.50,
    )
    db_session.add(po)
    # Duplicate supplier invoice number
    inv = m.PurchaseInvoice(
        tenant_id=tid,
        invoice_number="PI-DUP-1",
        supplier_id=supplier.id,
        supplier_invoice_number="INV-7788",
        status="draft",
        total_amount=10,
    )
    db_session.add(inv)
    await db_session.commit()

    sample = """
    Vendor: ACME Supplies Ltd
    Purchase Order PO-ACME-99
    Invoice No: INV-7788
    Date: 2026-03-15
    Total: GHS 250.50
    """

    monkeypatch.setattr(
        ocr_svc,
        "extract_text",
        lambda media: (sample, "pdf"),
    )

    headers = await _mgr(ac)
    # drop content-type so httpx sets multipart boundary
    headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    files = {"file": ("invoice.pdf", _blank_pdf(), "application/pdf")}
    data = {"document_type": "invoice", "expected_amount": "200"}
    r = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files=files,
        data=data,
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["method"] == "rule_based_ocr"
    assert body["extracted"]["amount"] == 250.50
    assert body["extracted"]["reference"] == "INV-7788"
    assert any(m_["party_id"] == supplier.id for m_ in body["matches"]["parties"])
    assert any(p["po_number"] == "PO-ACME-99" for p in body["matches"]["purchase_orders"])
    codes = {d["code"] for d in body["discrepancies"]}
    assert "amount_mismatch" in codes
    assert "duplicate_reference" in codes
    assert "Beta" not in r.text


@pytest.mark.asyncio
async def test_documents_analyze_tenant_isolation(client, db_session, monkeypatch):
    ac, seed = client
    beta_supplier = m.Party(
        tenant_id=seed["t2"].id,
        kind="supplier",
        name="Secret Beta Vendor XYZ",
        credit_limit=0,
    )
    db_session.add(beta_supplier)
    await db_session.commit()

    sample = """
    Payee: Secret Beta Vendor XYZ
    Date: 2026-04-01
    Total: GHS 10.00
    Invoice No: BETA-ONLY-1
    """
    monkeypatch.setattr(ocr_svc, "extract_text", lambda media: (sample, "pdf"))

    headers = await _mgr(ac)
    headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    r = await ac.post(
        "/api/v1/ai/documents/analyze",
        headers=headers,
        files={"file": ("r.pdf", _blank_pdf(), "application/pdf")},
        data={"document_type": "invoice"},
    )
    assert r.status_code == 200, r.text
    parties = r.json()["data"]["matches"]["parties"]
    assert all(p["name"] != "Secret Beta Vendor XYZ" for p in parties)
    assert "Secret Beta Vendor XYZ" not in str(parties)
    # may flag no_party_match
    assert "Secret Beta" not in r.text or r.json()["data"]["extracted"]["payee"]
    # response body should not leak beta party_id
    assert beta_supplier.id not in r.text
