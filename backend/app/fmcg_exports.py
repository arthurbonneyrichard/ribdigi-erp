"""Excel and PDF files for FMCG reports.

Excel: one sheet, bold header, frozen header row, column widths, money and number formats. Text
that starts with = + - or @ is stored as plain text so a spreadsheet can never run it as a formula.

PDF: dependency-free, landscape A4, as many pages as the table needs, the header repeated on every
page, "Page x of y" and the date made at the foot. It uses the built-in Courier font (accents outside
Latin-1 become ?), so columns line up exactly; long cells are cut with "..." and the full text is in
the Excel or CSV file.
"""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

PAGE_W, PAGE_H = 842, 595  # A4 landscape in points
MARGIN = 36
FONT = 8
CHAR_W = FONT * 0.6
LINE_H = 11
MAX_CELL = 40


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) >= 1000 or v != int(v) else str(int(v))
    return str(v)


def to_xlsx(report: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "".join(" " if ch in "[]:*?/\\" else ch for ch in (report["title"] or "Report"))[:31].strip() or "Report"
    row = 1
    ws.cell(row=row, column=1, value=report["title"]).font = Font(bold=True, size=14)
    row += 1
    if report.get("period"):
        ws.cell(row=row, column=1, value=f"{report['period']['start']} to {report['period']['end']}")
        row += 1
    for key, label in (("filters_text", "Filters"), ("note", "Note")):
        if report.get(key):
            ws.cell(row=row, column=1, value=f"{label}: {report[key]}")
            row += 1
    row += 1
    head = row
    cols = report["columns"]
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=head, column=i, value=c["label"])
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center" if c["kind"] != "text" else "left", wrap_text=True)
    widths = [len(c["label"]) for c in cols]
    for r_i, data in enumerate(report["rows"], head + 1):
        for i, c in enumerate(cols, 1):
            v = data.get(c["key"])
            cell = ws.cell(row=r_i, column=i)
            if isinstance(v, str):
                cell.value = v
                if v[:1] in ("=", "+", "-", "@", "\t", "\r"):
                    cell.data_type = "s"  # text, never a formula
            else:
                cell.value = v
            if _is_number(v):
                cell.number_format = "#,##0.00" if c["kind"] == "money" else "#,##0.###"
            widths[i - 1] = max(widths[i - 1], len(_text(v)))
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(w + 2, 10), 50)
    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    if report.get("truncated"):
        ws.cell(row=head + len(report["rows"]) + 2, column=1, value=f"Only the first {len(report['rows'])} of {report['row_count']} rows are shown.")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: max(n - 3, 1)] + "..."


def _layout(report: dict) -> tuple[list[str], list[int], list[list[str]]]:
    cols = report["columns"]
    labels = [c["label"] for c in cols]
    rows = [[_text(r.get(c["key"])) for c in cols] for r in report["rows"]]
    widths = [min(max([len(labels[i])] + [len(r[i]) for r in rows[:500]]), MAX_CELL) for i in range(len(cols))]
    avail = int((PAGE_W - 2 * MARGIN) / CHAR_W)
    gap = 2
    # Too wide for the page: shrink the widest columns until it fits (never below 6 characters).
    while sum(widths) + gap * (len(widths) - 1) > avail and max(widths) > 6:
        widths[widths.index(max(widths))] -= 1
    return labels, widths, rows


def to_pdf(report: dict) -> bytes:
    labels, widths, rows = _layout(report)
    kinds = [c["kind"] for c in report["columns"]]

    def line(cells: list[str]) -> str:
        out = []
        for i, c in enumerate(cells):
            t = _cut(c, widths[i])
            out.append(t.rjust(widths[i]) if kinds[i] != "text" else t.ljust(widths[i]))
        return "  ".join(out).rstrip()

    head = [report["title"]]
    if report.get("period"):
        head.append(f"{report['period']['start']} to {report['period']['end']}")
    for key in ("filters_text", "note"):
        if report.get(key):
            head.append(_cut(str(report[key]), int((PAGE_W - 2 * MARGIN) / CHAR_W)))
    per_page = int((PAGE_H - 2 * MARGIN - (len(head) + 3) * LINE_H) / LINE_H)
    per_page = max(per_page, 5)
    pages = [rows[i : i + per_page] for i in range(0, len(rows), per_page)] or [[]]
    made = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    objects: list[bytes] = []

    def add(b: bytes) -> int:
        objects.append(b)
        return len(objects)

    add(b"")  # 1 catalog, filled later
    add(b"")  # 2 pages, filled later
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold >>")
    page_ids: list[int] = []
    for n, chunk in enumerate(pages, 1):
        y = PAGE_H - MARGIN
        parts = []
        for i, h in enumerate(head):
            parts.append(f"BT /F2 {FONT + (4 if i == 0 else 0)} Tf {MARGIN} {y} Td ({_esc(h)}) Tj ET")
            y -= LINE_H + (4 if i == 0 else 0)
        y -= LINE_H // 2
        parts.append(f"BT /F2 {FONT} Tf {MARGIN} {y} Td ({_esc(line(labels))}) Tj ET")
        y -= LINE_H
        for r in chunk:
            parts.append(f"BT /F1 {FONT} Tf {MARGIN} {y} Td ({_esc(line(r))}) Tj ET")
            y -= LINE_H
        if not rows and n == 1:
            parts.append(f"BT /F1 {FONT} Tf {MARGIN} {y} Td (Nothing to show for this report.) Tj ET")
        foot = f"Page {n} of {len(pages)}   Made {made}"
        if report.get("truncated") and n == len(pages):
            foot += f"   Only the first {len(report['rows'])} of {report['row_count']} rows"
        parts.append(f"BT /F1 {FONT} Tf {MARGIN} {MARGIN - 14} Td ({_esc(foot)}) Tj ET")
        stream = "\n".join(parts).encode("latin-1", errors="replace")
        content = add(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream")
        page_ids.append(add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R /F2 {bold} 0 R >> >> >>".encode("ascii")
        ))
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(page_ids)} >>".encode("ascii")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)
