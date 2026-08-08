"""Parse bank CSV / OFX feeds into statement line dicts."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from fastapi import HTTPException

# Flexible CSV header aliases → canonical field
_DATE_HEADERS = {
    "date",
    "txn_date",
    "transaction_date",
    "posted",
    "posted_date",
    "value_date",
    "booking_date",
}
_AMOUNT_HEADERS = {"amount", "amt", "value", "transaction_amount"}
_DEBIT_HEADERS = {"debit", "withdrawal", "out", "money_out"}
_CREDIT_HEADERS = {"credit", "deposit", "in", "money_in"}
_DESC_HEADERS = {"description", "desc", "memo", "narration", "details", "payee", "name"}
_REF_HEADERS = {"ref", "reference", "external_ref", "fitid", "check_number", "cheque", "id"}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def _parse_date(value: str | None) -> datetime:
    text = (value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing transaction date")
    # OFX YYYYMMDD[HHMMSS[.XXX]]
    m = re.match(r"^(\d{8})(\d{6})?", text)
    if m and len(m.group(1)) == 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unrecognized date: {text}") from exc


def _parse_amount(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return None
    # (123.45) → -123.45 ; European 1.234,56
    neg = False
    if text.startswith("(") and text.endswith(")"):
        neg = True
        text = text[1:-1]
    text = text.replace(",", "") if text.count(",") == 1 and text.count(".") == 0 else text
    if re.search(r"\d,\d{2}$", text) and "." not in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {".", "-"}:
        return None
    amt = float(text)
    return -amt if neg else amt


def detect_format(filename: str | None, content: str) -> str:
    name = (filename or "").lower()
    head = content.lstrip()[:200].upper()
    if name.endswith(".ofx") or name.endswith(".qfx") or "OFXHEADER" in head or "<OFX>" in head:
        return "ofx"
    if name.endswith(".csv") or name.endswith(".txt"):
        return "csv"
    if "<STMTTRN>" in head or "<BANKTRANLIST>" in content.upper()[:2000]:
        return "ofx"
    return "csv"


def parse_csv_feed(content: str) -> dict:
    """Return {lines, opening_balance?, closing_balance?, format}."""
    sample = content.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    mapping: dict[str, str] = {}
    for raw in reader.fieldnames:
        key = _norm_header(raw)
        if key in _DATE_HEADERS and "date" not in mapping:
            mapping["date"] = raw
        elif key in _AMOUNT_HEADERS and "amount" not in mapping:
            mapping["amount"] = raw
        elif key in _DEBIT_HEADERS and "debit" not in mapping:
            mapping["debit"] = raw
        elif key in _CREDIT_HEADERS and "credit" not in mapping:
            mapping["credit"] = raw
        elif key in _DESC_HEADERS and "description" not in mapping:
            mapping["description"] = raw
        elif key in _REF_HEADERS and "external_ref" not in mapping:
            mapping["external_ref"] = raw

    if "date" not in mapping:
        raise HTTPException(status_code=400, detail="CSV must include a date column")
    if "amount" not in mapping and not ("debit" in mapping or "credit" in mapping):
        raise HTTPException(status_code=400, detail="CSV must include amount or debit/credit columns")

    lines: list[dict] = []
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue
        date_raw = row.get(mapping["date"])
        if "amount" in mapping:
            amount = _parse_amount(row.get(mapping["amount"]))
        else:
            debit = _parse_amount(row.get(mapping["debit"])) if "debit" in mapping else None
            credit = _parse_amount(row.get(mapping["credit"])) if "credit" in mapping else None
            if credit is not None and abs(credit) > 0:
                amount = abs(credit)
            elif debit is not None and abs(debit) > 0:
                amount = -abs(debit)
            else:
                continue
        if amount is None or abs(amount) < 1e-9:
            continue
        desc = (row.get(mapping["description"]) or "").strip() if "description" in mapping else ""
        ref = (row.get(mapping["external_ref"]) or "").strip() if "external_ref" in mapping else ""
        lines.append(
            {
                "txn_date": _parse_date(date_raw),
                "amount": round(amount, 2),
                "description": desc or None,
                "external_ref": ref or None,
            }
        )

    if not lines:
        raise HTTPException(status_code=400, detail="CSV contained no usable transaction rows")
    return {"format": "csv", "lines": lines, "opening_balance": None, "closing_balance": None}


def _ofx_tags(block: str) -> dict[str, str]:
    """Extract OFX SGML tags from a STMTTRN (or similar) block."""
    out: dict[str, str] = {}
    for m in re.finditer(r"<([A-Z0-9.]+)>([^<\r\n]*)", block, flags=re.IGNORECASE):
        out[m.group(1).upper()] = m.group(2).strip()
    return out


def parse_ofx_feed(content: str) -> dict:
    text = content.lstrip("\ufeff")
    # Strip binary OFX header before <OFX>
    idx = text.upper().find("<OFX>")
    if idx >= 0:
        text = text[idx:]

    opening = None
    closing = None
    bal = re.search(r"<LEDGERBAL>.*?<BALAMT>([^<\r\n]+)", text, flags=re.IGNORECASE | re.DOTALL)
    if bal:
        closing = _parse_amount(bal.group(1))
    # Some feeds expose available / statement balances
    for tag in ("BALAMT",):
        pass

    lines: list[dict] = []
    for m in re.finditer(r"<STMTTRN>(.*?)</STMTTRN>", text, flags=re.IGNORECASE | re.DOTALL):
        tags = _ofx_tags(m.group(1))
        # OFX 1.x often omits closing tags — also scan until next STMTTRN
        if not tags.get("TRNAMT") and not tags.get("DTPOSTED"):
            continue
        amount = _parse_amount(tags.get("TRNAMT"))
        if amount is None or abs(amount) < 1e-9:
            continue
        dt = tags.get("DTPOSTED") or tags.get("DTUSER") or tags.get("DTAVAIL")
        desc = tags.get("NAME") or tags.get("MEMO") or tags.get("PAYEE") or ""
        ref = tags.get("FITID") or tags.get("CHECKNUM") or tags.get("REFNUM") or ""
        lines.append(
            {
                "txn_date": _parse_date(dt),
                "amount": round(amount, 2),
                "description": desc.strip() or None,
                "external_ref": ref.strip() or None,
            }
        )

    # Fallback: unclosed STMTTRN blocks (common in OFX 1.x)
    if not lines:
        parts = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)
        for part in parts[1:]:
            chunk = re.split(r"<STMTTRN>|</BANKTRANLIST>|</STMTTRN>", part, flags=re.IGNORECASE)[0]
            tags = _ofx_tags(chunk)
            amount = _parse_amount(tags.get("TRNAMT"))
            if amount is None or abs(amount) < 1e-9:
                continue
            dt = tags.get("DTPOSTED") or tags.get("DTUSER")
            if not dt:
                continue
            desc = tags.get("NAME") or tags.get("MEMO") or ""
            ref = tags.get("FITID") or tags.get("CHECKNUM") or ""
            lines.append(
                {
                    "txn_date": _parse_date(dt),
                    "amount": round(amount, 2),
                    "description": desc.strip() or None,
                    "external_ref": ref.strip() or None,
                }
            )

    if not lines:
        raise HTTPException(status_code=400, detail="OFX contained no STMTTRN transactions")

    # Infer opening from closing − net when LEDGERBAL present
    if closing is not None:
        net = round(sum(float(ln["amount"]) for ln in lines), 2)
        opening = round(closing - net, 2)

    return {
        "format": "ofx",
        "lines": lines,
        "opening_balance": opening,
        "closing_balance": closing,
    }


def parse_bank_feed(content: str, *, filename: str | None = None) -> dict:
    fmt = detect_format(filename, content)
    if fmt == "ofx":
        return parse_ofx_feed(content)
    return parse_csv_feed(content)
