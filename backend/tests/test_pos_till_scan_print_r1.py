"""POS wedge scan, bold receipt, one print on Pay, Email/SMS opt-in."""

from __future__ import annotations

from pathlib import Path

from app.printers import pos_show_receipt_email_sms
from app.receipts import render_thermal_html, to_thermal_pdf
from tests.test_receipts import _sample_receipt

ROOT = Path(__file__).resolve().parents[2]


def _pos() -> str:
    return (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")


def test_wedge_scan_listener_does_not_steal_text_fields():
    pos = _pos()
    wedge = (ROOT / "frontend/lib/posWedgeScan.ts").read_text(encoding="utf-8")
    assert "consumeWedgeKey" in pos
    assert "addEventListener('keydown', onKey, true)" in pos
    assert "isPosTypingField" in wedge
    assert "WEDGE_KEY_GAP_MS = 50" in wedge
    assert "applyScannedBarcode" in pos
    assert "/pos/products/search" in pos


def test_receipt_print_font_is_bold():
    html = render_thermal_html(_sample_receipt(), paper="80mm")
    assert "font-weight:700" in html
    assert "max-width:80mm" in html
    assert "text-align:center" in html
    assert "Powered by RIBDIGI ERP" in html
    assert "font-size:5px" in html
    assert "window.print" not in html
    narrow = render_thermal_html(_sample_receipt(), paper="58mm")
    assert "max-width:58mm" in narrow
    pdf = to_thermal_pdf(_sample_receipt(), paper="80mm")
    assert pdf.startswith(b"%PDF")
    assert b"/Courier-Bold" in pdf
    pos = _pos()
    assert "font-weight:700" in pos


def test_pay_prints_receipt_once():
    pos = _pos()
    printer = (ROOT / "frontend/lib/posReceiptPrint.ts").read_text(encoding="utf-8")
    assert "printedPayIds" in pos
    assert pos.count("void printReceiptAfterPay(") == 2
    fail = pos.split("setMessage(`Sale ${r.data.reference} saved${extra}`);", 1)[1]
    fail = fail.split("async function saveQuoteOffline", 1)[0]
    assert "printReceiptAfterPay" not in fail
    assert "setLastSale(null);" in fail
    assert printer.count("frame.print()") == 1
    assert "window.open" not in printer
    assert "Allow pop-ups" not in (ROOT / "frontend/app/(dashboard)/printers/page.tsx").read_text(encoding="utf-8")
    assert "Choose a printer before the receipt can print." not in pos
    assert "PosPrintStatus" not in pos
    assert "setMessage(`Scanned" not in pos
    assert "barcode matches" not in pos


def test_email_sms_hidden_unless_option_on():
    pos = _pos()
    printers = (ROOT / "frontend/app/(dashboard)/printers/page.tsx").read_text(encoding="utf-8")
    assert "const [showReceiptEmailSms, setShowReceiptEmailSms] = useState(false);" in pos
    assert "showReceiptEmailSms && !lastSale.offline" in pos
    assert "Add Email and SMS receipt actions to POS" in printers
    assert "See installed printers" in printers
    assert "Add to printers used for POS" in printers
    assert "cannot list every printer" in printers
    assert pos_show_receipt_email_sms(None) is False
    tenant = type("T", (), {"print_branding": {}})()
    assert pos_show_receipt_email_sms(tenant) is False
    tenant.print_branding = {"pos_show_receipt_email_sms": True}
    assert pos_show_receipt_email_sms(tenant) is True
