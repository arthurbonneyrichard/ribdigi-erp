"""Downloadable live-test script for Retail, Pharmacy, and Wholesale."""

from __future__ import annotations

from datetime import datetime


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 92) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def script_lines() -> list[str]:
    """Operator checklist. Each step is a pass only when the screen matches it."""
    sections = [
        (
            "How to use this script",
            [
                "Use one company per industry: Retail, Pharmacy, Wholesale, and Retail + Wholesale.",
                "Write the document number and the stock quantity next to each step.",
                "A step passes only when the screen shows the result written here.",
                "Mobile Money stores the amount and reference. It does not collect the money.",
                "A credit sale is money still owed. Cash is recorded only when a payment is posted.",
                "Paid self-serve checkout is not part of this test.",
                "Prescription counts cover the whole pharmacy company. They are not split by store.",
            ],
        ),
        (
            "Retail",
            [
                "1. Sign in to the retail company. Open Inventory and add a product with a selling price and quantity at the store you will sell from.",
                "2. Open POS, start a shift, and enter the opening cash you counted.",
                "3. Add that product. Set the payment to Cash. Complete the sale.",
                "4. The receipt shows a POS sale number. The store quantity is lower by the quantity sold.",
                "5. Open Reports for today. The sale is in today's sales for that store. A sale at another store is not included when your account is assigned to one store.",
                "6. Record a sellable return for that sale. The quantity returns to the same store. A discard return does not put the quantity back.",
                "7. Close the shift. Expected cash is opening cash plus cash sales minus cash refunds.",
            ],
        ),
        (
            "Pharmacy",
            [
                "1. Sign in to the pharmacy company. Add an Rx-only medicine with a batch number and an expiry date.",
                "2. Open Prescriptions and record a new prescription for that medicine.",
                "3. Move it through review to approved. Dispense only part of the quantity.",
                "4. The prescription status is partially dispensed. The batch quantity fell by the dispensed amount.",
                "5. On the dashboard Pharmacy section, Ready to dispense, Partially dispensed, Low stock, and Nearing expiry match the records you just made.",
                "6. Dispense the remaining quantity. The status becomes dispensed.",
                "7. Place a quarantine or recall hold on a batch. That batch cannot be dispensed while the hold is open.",
                "8. Open the expiry report. The batch you created is listed when its expiry is inside the report window.",
            ],
        ),
        (
            "Wholesale",
            [
                "1. Sign in to the wholesale company. Add a product with stock and a wholesale price.",
                "2. Create a quote for a customer, then accept it and convert it to a sales order.",
                "3. Fill only part of the order quantity. Stock falls by the filled quantity. The order shows that quantity as fulfilled.",
                "4. Invoice the order. Stock does not fall again for the quantity already filled.",
                "5. The invoice balance stays open until you record a customer payment. After the payment, the open balance is lower by that amount.",
                "6. A minimum order quantity and a quantity price tier apply on the wholesale order. They do not apply on a retail POS sale.",
            ],
        ),
        (
            "Retail and Wholesale together",
            [
                "1. Sign in to a Retail + Wholesale company.",
                "2. Complete a cash sale on POS. That sale stays a retail sale.",
                "3. Create a quote and sales order on Sales. That order stays a wholesale order.",
                "4. POS refuses to check out the wholesale order. Sales does not turn the POS receipt into a wholesale quote.",
                "5. Both channels use the same product. Each movement changes that product's stock once.",
            ],
        ),
        (
            "Purchasing, tax, and reports",
            [
                "1. Create a purchase order for the selling store, receive the goods, and confirm stock increased at that store.",
                "2. Open the tax report for the same day. Output tax includes the retail or wholesale sale you posted. It excludes a sale at a store your user cannot access.",
                "3. Export the same report. The file contains the same totals as the screen.",
            ],
        ),
        (
            "Record the result",
            [
                "Pass: every numbered step matched the screen, and you wrote the document number and quantity.",
                "Fail: any quantity moved twice, a store user saw another store, or a payment was marked collected when no payment was posted.",
                "Stop the live test on the first fail and note the page, the document number, and the quantities you saw.",
            ],
        ),
    ]
    lines = [
        "RIBDIGI live test: Retail, Pharmacy, and Wholesale",
        f"Prepared {datetime.utcnow().date().isoformat()}",
        "",
    ]
    for title, steps in sections:
        lines.append(title)
        for step in steps:
            lines.extend(_wrap(step))
            lines.append("")
        lines.append("")
    return lines


def to_pdf(lines: list[str]) -> bytes:
    """Multi-page Helvetica PDF. No third-party PDF library."""
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap(line) if len(line) > 92 else [line])
    per_page = 44
    pages = [wrapped[i : i + per_page] for i in range(0, len(wrapped), per_page)] or [[""]]
    page_count = len(pages)
    font_id = 3
    contents: list[bytes] = []
    for rows in pages:
        commands = ["BT /F1 11 Tf 50 760 Td (RIBDIGI live test script) Tj ET"]
        y = 738
        for row in rows:
            commands.append(f"BT /F1 9 Tf 50 {y} Td ({_escape(row[:110])}) Tj ET")
            y -= 14
        contents.append("\n".join(commands).encode("latin-1", errors="replace"))

    objects: list[bytes] = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"",
        b"3 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    kids: list[str] = []
    for index, stream in enumerate(contents):
        page_id = 4 + index * 2
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        objects.append(
            (
                f"{page_id} 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>endobj\n"
            ).encode("ascii")
        )
        objects.append(
            f"{content_id} 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )
    objects[1] = (
        f"2 0 obj<< /Type /Pages /Kids [{' '.join(kids)}] /Count {page_count} >>endobj\n"
    ).encode("ascii")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def build_live_test_pdf() -> bytes:
    return to_pdf(script_lines())
