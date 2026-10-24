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

## Instagram feed posts

Four 1080 × 1440 px (3:4 portrait) posts for the same launch.

| File | Concept |
| --- | --- |
| `Ribdigi_ERP_Instagram_Flyer_01` | Launch announcement: "Ribdigi ERP is launching" over a 2 November 2026 calendar page |
| `Ribdigi_ERP_Instagram_Flyer_02` | Busy retailer: notes, receipts and a calculator turn into the real ERP dashboard on a phone |
| `Ribdigi_ERP_Instagram_Flyer_03` | The real product: the point-of-sale and purchasing screens, labelled |
| `Ribdigi_ERP_Instagram_Flyer_04` | Retail shops: supermarkets, mini-marts, phone, electrical, fashion, cosmetics and hardware shops |

Each has a `.png` ready to post and its editable `.html` source. Shared styles are in `ig-base.css`; the font is the ERP's Plus Jakarta Sans in `assets/fonts/`, so no internet is needed to render. `assets/erp-phone-01-dashboard.png` is the real ERP dashboard at phone width (Demo Mart demo data).

Re-render after editing a source file:

```
node render-instagram.js          # all four
node render-instagram.js 03       # just one
```

The script also lists any text that falls outside the 60 px safe margin.
