# Wholesale business type

Wholesale was removed as a choice on 12 Oct 2026 (customer desks narrowed to retail, hotel and restaurant) and brought back on 13 Nov 2026 as **the retail desk with wholesale selling**. It is not a separate desk: a wholesale company uses the retail screens, the retail database (`desks.desk_for_industry("wholesale") == "retail"`) and the retail dashboard, plus the wholesale panel (open quotes, open orders, reserved stock, money owed).

What is different from retail (`backend/app/trade.py`):

- **Channel:** every sale is on the wholesale channel, at the POS counter and on quotes, orders and invoices. Wholesale-channel prices apply.
- **Quantity price tiers:** Inventory → product → price tiers (minimum quantity → unit price, optionally per customer group). Quotes, orders and invoices use the tier for the quantity.
- **Minimum order quantity:** Inventory → product → "Wholesale MOQ"; a sales line under it is refused.
- **Credit trade customers:** customer credit limits, payment terms and statements as in retail (Credit).
- **Units:** cartons / packs through units of measure with conversion ratios (Inventory → Catalog → Units).
- HR is on (same HR areas as retail). Online store, gift cards and other desks are off.

Codes: `wholesale` in `tenants.VALID_INDUSTRIES`, `PROVISION_INDUSTRIES`, `packages.CANONICAL_INDUSTRIES` (alias `wholesaler`), `schemas.IndustryValue`; dashboard layout maps it to `retail`. The older combined type `retail_wholesale` (retail counter + wholesale desk) stays retired; its code paths in `trade.py` remain for any stored company.

Billing: wholesale uses the general package prices unless the software owner sets wholesale prices (Platform → Billing → package Industry).
