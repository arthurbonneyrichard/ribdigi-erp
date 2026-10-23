# Ribdigi ERP launch flyers

Four A4 portrait flyers for the 2 November 2026 launch.

| File | Concept |
| --- | --- |
| `Ribdigi_ERP_Launch_Flyer_01` | Launch announcement: "Ribdigi ERP is launching", 2 November 2026 |
| `Ribdigi_ERP_Launch_Flyer_02` | The busy retailer: products, purchases, sales and reports in one place |
| `Ribdigi_ERP_Launch_Flyer_03` | Product and sales focus: the real point-of-sale screen |
| `Ribdigi_ERP_Launch_Flyer_04` | Retail shops: supermarkets, mini-marts, phone, electrical, fashion, cosmetics, hardware |

Each flyer has a `.png` (2481 × 3509 px, 300 dpi), a print-ready `.pdf` (A4, no margins, backgrounds on) and its editable `.html` source. Shared styles are in `flyer-base.css`.

- `assets/ribdigi-erp-logo-light-text.png` is `frontend/public/brand/logo-full.png` (white lettering, for dark backgrounds).
- `assets/ribdigi-erp-logo-dark-text.png` is `frontend/public/brand/logo-full-dark.png` (dark lettering, for light backgrounds).
- `assets/erp-*.png` are screenshots of the real ERP (Demo Mart demo company), taken at 2x.

Re-render after editing a source file (needs Chrome and `playwright-core`):

```
node render.js            # all four
node render.js 02 03      # just these
```

The flyers load the Plus Jakarta Sans font from Google Fonts, so render with an internet connection.
