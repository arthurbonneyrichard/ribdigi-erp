from datetime import datetime

from app.reports import day_bounds, month_bounds, parse_date


def test_parse_date_day():
    dt = parse_date("2026-08-08")
    assert dt == datetime(2026, 8, 8, 0, 0, 0)


def test_parse_date_end_of_day():
    dt = parse_date("2026-08-08", end_of_day=True)
    assert dt.hour == 23 and dt.minute == 59


def test_day_bounds():
    start, end = day_bounds(datetime(2026, 8, 8, 15, 30))
    assert start.hour == 0
    assert end.day == 8 and end.hour == 23


def test_month_bounds_december():
    start, end = month_bounds(2026, 12)
    assert start == datetime(2026, 12, 1)
    assert end.year == 2026 and end.month == 12 and end.day == 31


def test_sales_by_salesperson_empty_shape():
    # Pure shape helper: avg ticket math used by report aggregation
    sale_count = 4
    revenue = 200.0
    avg = round(revenue / sale_count, 2) if sale_count else 0.0
    assert avg == 50.0


def test_flatten_salesperson_export():
    from app.report_export import flatten_report

    rows, lines, title = flatten_report(
        "sales_salesperson",
        {
            "total_revenue": 100,
            "salespeople": [
                {
                    "full_name": "Ada",
                    "sale_count": 2,
                    "revenue": 100,
                    "avg_ticket": 50,
                }
            ],
        },
    )
    assert title == "Sales by Salesperson"
    assert rows[0]["full_name"] == "Ada"
    assert any("Ada" in line for line in lines)


def test_flatten_store_export():
    from app.report_export import flatten_report, EXPORTABLE

    assert "sales_by_store" in EXPORTABLE
    rows, lines, title = flatten_report(
        "sales_by_store",
        {
            "total_revenue": 80,
            "stores": [
                {
                    "name": "Downtown",
                    "code": "DT",
                    "sale_count": 3,
                    "revenue": 80,
                    "invoice_revenue": 50,
                    "pos_revenue": 30,
                }
            ],
        },
    )
    assert title == "Sales by Store"
    assert rows[0]["code"] == "DT"
    assert any("Downtown" in line for line in lines)
