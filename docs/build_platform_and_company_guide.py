#!/usr/bin/env python3
"""Build the platform-console and company setup step-by-step PDF."""

import importlib.util
from pathlib import Path

SRC = Path(__file__).resolve().parent / "build_customer_user_guide.py"
OUT = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "public"
    / "guides"
    / "RIBDIGI-ERP-Platform-and-Company-Guide.pdf"
)

_spec = importlib.util.spec_from_file_location("customer_guide", SRC)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

GREEN = _mod.GREEN
INK = _mod.INK
MUTED = _mod.MUTED


class Guide(_mod.Guide):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*GREEN)
        self.cell(0, 8, "RIBDIGI ERP  ·  Platform and Company Guide", align="L")
        self.ln(10)


def build() -> None:
    pdf = Guide()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("DejaVu", "", _mod.FONT)
    pdf.add_font("DejaVu", "B", _mod.FONT_B)
    pdf.add_page()

    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 0, 210, 42, "F")
    pdf.set_xy(14, 12)
    pdf.set_font("DejaVu", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "RIBDIGI ERP")
    pdf.ln(9)
    pdf.set_x(14)
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 8, "Platform Console and Company Setup")
    pdf.ln(18)
    pdf.set_text_color(*MUTED)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_x(14)
    pdf.cell(0, 6, "Step by step.   ·   A Ribdigi House Product")
    pdf.ln(12)

    pdf.h2("How to use this guide")
    pdf.p(
        "Part 1 is for the software owner and platform staff. You create each company, "
        "set its package, and hand the company its own workspace. You do not add products there."
    )
    pdf.p(
        "Part 2 is for the company administrator. Sign in with the company slug, then follow "
        "the steps in order: company profile, tax, catalog, products, opening stock, sales, "
        "the till, purchasing, expenses, stores, and staff."
    )
    pdf.p(
        "A shorter everyday guide is also on the sign-in page: Download user guide (PDF). "
        "This document is the setup sequence."
    )

    pdf.h1("Part 1. Platform console")

    pdf.h2("1. Sign in as the owner")
    pdf.steps([
        "Open the Ribdigi ERP address.",
        "Workspace: platform.",
        "Email and password of the platform owner account.",
        "If two-factor authentication is on, enter the 6-digit code from the authenticator app.",
    ])
    pdf.p(
        "Every platform staff account uses the same workspace, platform. A company never uses "
        "platform. After you create a company, that company signs in with its own slug."
    )

    pdf.h2("2. Menus on the owner workspace")
    pdf.bullets([
        "Platform — create companies, assign packages, turn modules on or off, suspend or activate.",
        "Staff — add Ribdigi staff who may open this console.",
        "Reports — all companies: status, packages, subscription usage, renewals, and trials.",
        "Jobs, Users, Notifications, Audit, and Security — owner tools, not a shop till.",
    ])
    pdf.p("Products, sales, and stock are not done on this workspace.")

    pdf.h2("3. Create a company")
    pdf.p("Open Platform. Use the Create tenant form.")
    pdf.steps([
        "Company name — the legal or trading name, for example Sunrise Mart Ltd.",
        "Slug — filled from the name. Keep it short, lowercase, with hyphens, for example sunrise-mart. This is the workspace the company types at sign-in. It cannot be shared with another company.",
        "Industry — choose the closest option.",
        "Currency — the currency the company will use on documents.",
        "Admin email — the first company administrator.",
        "Admin password — at least 8 characters, with an uppercase letter, a lowercase letter, a number, and a symbol.",
        "Click Create tenant.",
    ])
    pdf.p(
        "Send the company administrator three things: the workspace slug, the admin email, and "
        "the password. They sign in on the same site. Ask them to change the password under Security."
    )

    pdf.h2("4. Assign the package and term")
    pdf.p(
        "Creating the company does not set a paid term. Assign it next. This console records "
        "the entitlement. It does not take card or mobile-money payment."
    )
    pdf.steps([
        "In Tenant management, find the company row.",
        "Click Manage. The page moves to Subscription & features. A banner shows the company name and slug.",
        "Package — choose the plan.",
        "Term length — a number from 1 to 120.",
        "Term unit — Months or Years.",
        "Start date — leave blank to start now, or type YYYY-MM-DD.",
        "Store entitlement override — leave blank to use the package store limit. Fill it only when this company may have a different number of stores.",
        "Click Assign package & term.",
    ])
    pdf.p(
        "The panel then shows months assigned, used, remaining, and the renewal date. "
        "If you only need to change the store limit later, use Save store override. "
        "A blank override clears it back to the package default."
    )

    pdf.h2("5. Choose which menus the company can open")
    pdf.steps([
        "Stay on the same Manage panel. Scroll to Feature modules.",
        "Tick the modules this company should use: inventory, sales, pos, purchasing, and the rest.",
        "Dashboard, notifications, and security stay on. You cannot turn those off.",
        "Click Save feature modules.",
        "Click Reset to package default if you want the plan's standard set back.",
    ])
    pdf.p("A company user will not see a menu you leave unticked, even if their role would allow it.")

    pdf.h2("6. Suspend or activate a company")
    pdf.steps([
        "Type a Suspend reason in the box above the table. The reason is required.",
        "On the company row, click Suspend.",
        "To restore access, click Activate.",
    ])
    pdf.p("Use the status chips at the top (All, Active, Trial, Grace, Suspended) to filter the list.")

    pdf.h2("7. Add platform staff")
    pdf.p("Open Staff. This is for people who work the owner console, not shop cashiers.")
    pdf.steps([
        "Under Add staff user, enter full name, email, and password.",
        "Choose a platform role such as support, admin, or finance.",
        "Phone is optional. Use international form, for example +233...",
        "Submit the form. The new person signs in with workspace platform and that email.",
        "Deactivate a person who leaves. Do not share the owner password.",
    ])
    pdf.p(
        "You can also grant the owner dashboard to an existing app user, or revoke that access. "
        "Revoke does not delete the person."
    )

    pdf.h2("8. Read platform reports")
    pdf.p(
        "Open Reports. You see every company: how many are active, on trial, in grace, or "
        "suspended, which package they are on, and which renewals or trials end soon. "
        "This is not a sales or stock report for one shop."
    )

    pdf.h2("9. Hand the company over")
    pdf.bullets([
        "Confirm the slug, admin email, package, term, and modules.",
        "Tell the administrator to follow Part 2 of this guide.",
        "Do not create products, invoices, or stock movements while signed in as platform.",
    ])

    pdf.h1("Part 2. Company setup")

    pdf.h2("10. Sign in as the company")
    pdf.steps([
        "Open the same Ribdigi ERP address.",
        "Workspace — the slug from Create tenant, for example sunrise-mart. Do not type platform.",
        "Email and password the owner set for the company administrator.",
        "Open Security and change a temporary password before you add staff.",
    ])
    pdf.p(
        "The left menu shows only modules in the package and your role. If Inventory or Sales "
        "is missing, ask the platform owner to tick that module and assign the package."
    )

    pdf.h2("11. Company profile")
    pdf.p("Open Company and fill the profile used on invoices and receipts.")
    pdf.steps([
        "Trading name and legal name.",
        "Registration number, contact person, phone, email, and website.",
        "Headquarters, billing, and shipping addresses.",
        "Industry, currency, and timezone.",
        "Fiscal year start, tax jurisdiction, and TIN or VAT number.",
        "Date format, time format, and decimal and thousand separators.",
        "Upload a logo if you want it on the sidebar and printouts.",
        "Under Print branding, set header and footer text, the invoice template, and receipt paper.",
        "Click Save company profile, and Save print branding.",
    ])
    pdf.p("If the page asks you to activate the company, click Activate before you sell.")

    pdf.h2("12. Tax rates")
    pdf.p("Open Tax before you price products, if the company charges tax.")
    pdf.steps([
        "Under Create rate, enter a name, for example VAT.",
        "Enter the rate as a percent.",
        "Choose the type: VAT, GST, Sales tax, or Custom.",
        "Exclusive means tax is added on top of the price. Inclusive means the price already includes tax.",
        "Leave reverse charge and the JSON box alone unless your accountant told you to use them.",
        "Click Add rate.",
    ])

    pdf.h2("13. Catalog, before the first product")
    pdf.p("Open Inventory, then the Catalog tab. Create these once. Products pick from this list.")
    pdf.h2("Units")
    pdf.steps([
        "Code, for example PCS, and Name, for example Piece.",
        "Leave Base unit blank for a root unit. For a pack, choose the base and the ratio (1 box = 12 pieces).",
        "Click Add unit.",
    ])
    pdf.h2("Categories")
    pdf.steps([
        "Code and Name, for example BEV and Beverages.",
        "Parent — leave blank for a top-level category, or choose a parent to nest it.",
        "Tax rate — optional. A product with its own rate overrides this.",
        "Click Add category.",
    ])
    pdf.h2("Brands")
    pdf.steps([
        "Code, name, and an optional description.",
        "Click Add brand. You can add a logo on the brand after it exists.",
    ])

    pdf.h2("14. Add a product")
    pdf.p("Stay on Inventory. Open the Products tab. Use Add product.")
    pdf.steps([
        "Name — required.",
        "SKU — leave blank to let the system assign one, or type your own.",
        "Barcode — optional. 4 to 48 characters: letters, numbers, hyphen, dot, or underscore.",
        "Description — optional.",
        "Actual price — what the item costs you.",
        "Selling price — what you charge.",
        "Weight and size — optional, in kilograms and centimetres.",
        "Category, Brand, and Unit — choose what you created. You can leave brand or unit blank.",
        "Tax class — standard-rated, zero-rated, or exempt.",
        "Tax rate — choose the rate, or leave blank to use the category or company default.",
        "Click Create product.",
    ])
    pdf.p(
        "The new row appears in the product table. Stock is still zero. Selling with no stock "
        "fails or goes negative only if your process allows it, so record opening stock or a purchase next."
    )

    pdf.h2("15. Picture, barcode, and deactivate")
    pdf.steps([
        "At the top of Inventory, open Selected product and choose the item.",
        "Add gallery image — PNG, JPEG, WebP, or GIF, up to 5 pictures. The first one is primary. Use Set primary to change it.",
        "Barcode — type or scan, or click Generate product barcode, then Print product barcode label.",
        "Change cost, selling price, category, or tax, then click Save product.",
        "Click Deactivate to hide the item from sales, purchasing, and POS. Stock tools still work. Click Activate to bring it back.",
    ])
    pdf.p(
        "Lookup tab: scan a barcode or search name or SKU, then Select. That loads warehouse stock "
        "and selects the product for the tools above."
    )

    pdf.h2("16. Put quantity on hand")
    pdf.p("Use this when the shop already holds stock on the first day. Select the product first.")
    pdf.steps([
        "Selected product — choose the item. Opening stock refuses to post if this is blank.",
        "Open the Opening stock tab.",
        "Warehouse — choose the store warehouse, or leave blank.",
        "Quantity, and unit if it is not the product default.",
        "Unit cost — blank uses the product actual price.",
        "Batch number, manufacturing date, and expiry date — only for items you track that way. Dates are YYYY-MM-DD.",
        "Reference — leave blank to get the next opening-stock number.",
        "Click Post opening stock.",
    ])
    pdf.p(
        "Later corrections: Stock counts to count the shelf, then complete the count. "
        "Adjust for a one-off correction. Stock Out for goods that leave without a sale. "
        "Transfers to move quantity from one warehouse to another. Do not type a new product to fix a count."
    )

    pdf.h2("17. Many products at once")
    pdf.steps([
        "Create categories, brands, and units first. The file cannot invent them.",
        "Inventory, Import tab, Download CSV template.",
        "Fill one row per product. Do not rename the columns.",
        "Choose the file, click Validate, and fix every error row.",
        "When the report says the file can be committed, click Import valid rows. A failed row blocks the whole file.",
        "Export products CSV any time you want a copy of the catalog.",
    ])

    pdf.h2("18. Customer, then a sale")
    pdf.p("Open Sales.")
    pdf.steps([
        "Under Customer, enter the customer name and the other fields you use, then click Add customer. Walk-in sales can skip a named customer when the form allows it.",
        "Under Create sale, choose the product, quantity, and price. Add tax if it is not already filled.",
        "Click Create invoice. That saves a draft. Stock does not move yet.",
        "On the draft row, click Post. Stock decreases when the invoice is posted.",
        "Record the amount paid. Unpaid balance stays as credit on Credit until you record a later payment.",
    ])
    pdf.p(
        "A quotation is only a price offer. It does not reduce stock. A sales return is created "
        "under Create return; stock comes back when the return is posted, not while it is a draft."
    )

    pdf.h2("19. Sell at the till")
    pdf.steps([
        "Open POS. Confirm the store at the top of the screen.",
        "Enter opening cash if asked, then click Open shift.",
        "Search or scan a product and add it to the cart. Change quantity or a line discount if needed.",
        "Payment: Cash, Card, Digital wallet, or Credit. Split tender is cash plus card.",
        "Click Charge · Complete sale. Print or share the receipt from the success screen.",
        "At the end of the day, click Shift report, then Close shift.",
        "Sign out. Do not leave a shift open on a shared till.",
    ])

    pdf.h2("20. Buy stock from a supplier")
    pdf.p("Open Purchasing. Tabs are Requests, Orders, GRNs, Invoices, and Returns.")
    pdf.steps([
        "On Orders, Quick add supplier: name, optional code, and type (Registered, Trade, Manufacturer, or Service). Click Add.",
        "Create purchase order: select the supplier and the product, quantity, and cost. Click Create draft PO.",
        "Send or approve the order using the actions on that row when your process requires it.",
        "When goods arrive, open the order and click Post GRN (accept / reject), or Receive all accepted. Stock increases by the accepted quantity.",
        "On Invoices, create the supplier invoice from the goods receipt, or create a manual invoice, and record the payment. Partial payments are allowed.",
        "On Returns, create a purchase return when goods go back. Stock decreases when that return is completed.",
    ])

    pdf.h2("21. Expenses")
    pdf.steps([
        "Open Expenses. Add a category first if you need one (rent, utilities, transport).",
        "Enter the amount, category, date, and payment method: Cash, Bank transfer, Card, or Cheque.",
        "Click Submit expense.",
        "If approval is on, a manager approves it before it is final. Recurring expenses are set by an administrator.",
    ])

    pdf.h2("22. More than one shop")
    pdf.p("Open Multi-Store. The package limits how many stores you can create.")
    pdf.steps([
        "Create a branch if you group shops that way, then a department if you use departments.",
        "New store: code, name, address, and phone. Click Create store.",
        "New warehouse for that store if stock is held in a named warehouse. Click Create warehouse.",
        "Use the store switcher in the top bar before you sell, count, or receive goods.",
        "Move goods with a transfer, not by editing the quantity on the product.",
    ])

    pdf.h2("23. Add company staff")
    pdf.p("Open Users. These people use the company slug, not platform.")
    pdf.steps([
        "Full name, email, and a strong password.",
        "Phone is optional.",
        "Role — company admin, store manager, sales officer, inventory officer, accountant, cashier, or a custom role.",
        "Branch and department — optional. Set them when the person must not see the whole company.",
        "Click Create user.",
        "Tell them the workspace slug, email, and password. Deactivate the user when they leave. Do not share one login.",
    ])
    pdf.p(
        "Cashiers typically see Dashboard, Inventory, POS, Sales, Notifications, and Security. "
        "Hiding a menu is not the only control. The server also checks permission."
    )

    pdf.h2("24. First week, in order")
    pdf.steps([
        "Owner: create the company, assign the package and term, tick modules, send the slug.",
        "Company admin: sign in, save Company, add tax rates.",
        "Add units, categories, and brands.",
        "Add products, or import the CSV after a clean Validate.",
        "Post opening stock, or receive a purchase.",
        "Add a customer and post one test invoice. Confirm stock went down.",
        "Open a POS shift, complete one cash sale, and close the shift.",
        "Add cashiers and managers. Sign out.",
    ])

    pdf.h2("25. If a step will not complete")
    pdf.bullets([
        "Create tenant fails: the slug is already used, or the password is missing upper, lower, number, or symbol.",
        "Manage seems to do nothing: click Manage again and scroll to Subscription & features. The panel opens under the table.",
        "Company cannot see Inventory: the module is off, or the user's role cannot read it.",
        "Create product is disabled: the name is empty.",
        "Import is blocked: Validate still has error rows, or category, brand, or unit in the file does not exist.",
        "Opening stock says select a product: choose Selected product first.",
        "Stock did not change: the invoice, return, or goods receipt is still a draft. Click Post.",
        "You land back on the sign-in page: sign in again with the company slug, not an email in the workspace box.",
    ])

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0,
        5,
        "Ribdigi ERP records payment information. It does not receive, hold, or settle funds. "
        "This guide does not replace your company procedures or tax advice.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(OUT)


if __name__ == "__main__":
    build()
