# Tenant Test Results — Retail scope

**Date:** 18 October 2026  
**Environment:** Windows; in-memory SQLite; `RATE_LIMIT_BACKEND=memory`; `ribdigi_erp` not opened

## Completion evidence

| Command | Result |
| --- | --- |
| `pytest tests/test_sales_return_credit_note.py tests/test_retail_audit_completion_r1.py tests/test_retail_pos_arithmetic_fixture.py tests/test_handbook_grn_receive_r1.py tests/test_cashier_pos_only.py -q` | **18 passed** |
| Same + `test_trade_channels.py::test_pharmacy_rx_activity_report` | **19 passed** in ~70s |

## Prior (not re-run in full)

| Suite | Result |
| --- | --- |
| Broad retail proof | **76 passed** |
| Security named suite | **123 passed** |
| `npm run test:offline` | **21 passed** |

## Counts

| Metric | Value |
| --- | ---: |
| Tests passed (this stream retail) | 18–19 |
| Tests failed | 0 |
