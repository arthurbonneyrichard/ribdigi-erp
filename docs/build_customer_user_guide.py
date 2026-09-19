#!/usr/bin/env python3
"""Build the customer-facing Ribdigi ERP user guide PDF."""

from pathlib import Path

from fpdf import FPDF

# Not under frontend/public — the file is served only to a company admin.
OUT = Path(__file__).resolve().parents[1] / "frontend" / "guides" / "RIBDIGI-ERP-Customer-User-Guide.pdf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

GREEN = (0, 107, 46)
INK = (16, 33, 27)
MUTED = (58, 86, 72)


class Guide(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*GREEN)
        self.cell(0, 8, "RIBDIGI ERP  ·  Customer User Guide", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-14)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"A Ribdigi House Product   ·   Page {self.page_no()}", align="C")

    def h1(self, text: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "B", 16)
        self.set_text_color(*GREEN)
        self.multi_cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, text: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "B", 12)
        self.set_text_color(*INK)
        self.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def p(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def bullets(self, items: list[str]):
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        for item in items:
            self.set_x(self.l_margin)
            self.multi_cell(0, 5.6, "-  " + item, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def steps(self, items: list[str]):
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(*INK)
        for i, item in enumerate(items, 1):
            self.set_x(self.l_margin)
            self.multi_cell(0, 5.6, f"{i}.  {item}", new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)


def build() -> None:
    pdf = Guide()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("DejaVu", "", FONT)
    pdf.add_font("DejaVu", "B", FONT_B)
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
    pdf.cell(0, 8, "Customer User Guide")
    pdf.ln(18)
    pdf.set_text_color(*MUTED)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_x(14)
    pdf.cell(0, 6, "One System. Total Business Control.   ·   A Ribdigi House Product")
    pdf.ln(12)

    pdf.h2("Who this guide is for")
    pdf.p(
        "This guide is for company staff: administrators, managers, cashiers, and everyone "
        "who sells, stocks, or buys in a company workspace. It is a step-by-step for setup "
        "and for a normal day. Your company administrator downloads it from the Dashboard "
        "and can share this file. Other roles do not see a download in the app."
    )

    pdf.h1("1. Sign in")
    pdf.p("Open the Ribdigi ERP address your company gave you. On the sign-in page enter:")
    pdf.bullets([
        "Workspace — your company slug (not an email). Example: sunshine-mart.",
        "Email — the address on your user account.",
        "Password — the password set for you.",
    ])
    pdf.p(
        "The platform owner uses workspace platform. Everyone who works inside a company uses "
        "that company's own slug. Two companies never share a workspace."
    )
    pdf.p("If you forget your password, use Forgot password, then the link sent to your email.")
    pdf.p(
        "If your company requires two-factor authentication, enter the 6-digit code from your "
        "authenticator app after your password. You can turn this on under Security."
    )

    pdf.h1("2. After you sign in")
    pdf.bullets([
        "The left menu is your navigation. Only modules included in your package and role appear.",
        "The top bar shows notifications, your name, theme (light or dark), and Log out.",
        "Theme is personal. Your choice does not change anyone else's screen.",
        "If your company has more than one store, use the store switcher so reports and stock match the store you are working in.",
        "Sign out when you finish, especially on a shared till.",
    ])

    pdf.h1("3. Dashboard")
    pdf.p(
        "Dashboard is the morning view of the business: sales, purchases, expenses, stock alerts, "
        "and recent activity. Cards are links. Select a card to open the related list or report. "
        "Trial or grace messages, when shown, tell you how long the company subscription has left."
    )

    pdf.h1("4. Company")
    pdf.p("Company holds the business profile used on documents and the sidebar:")
    pdf.bullets([
        "Legal name, registration, contact person, phone, email, and website.",
        "Billing and shipping addresses.",
        "Logo, date format, and currency display.",
        "Invoice numbering and print header or footer, where your role allows it.",
    ])

    pdf.h1("5. Catalog, before the first product")
    pdf.p("Open Inventory, then the Catalog tab. Do this once. Products pick from these lists.")
    pdf.h2("Units")
    pdf.steps([
        "Code, for example PCS, and Name, for example Piece.",
        "Leave Base unit blank for a root unit. For a pack, choose the base and the ratio, such as 1 box = 12 pieces.",
        "Click Add unit.",
    ])
    pdf.h2("Categories")
    pdf.steps([
        "Code and Name, for example BEV and Beverages.",
        "Parent — leave blank for a top-level category, or choose a parent to nest it.",
        "Tax rate — optional. A product with its own rate overrides the category.",
        "Click Add category.",
    ])
    pdf.h2("Brands")
    pdf.steps([
        "Code, name, and an optional description.",
        "Click Add brand. You can add a logo on the brand after it exists.",
    ])

    pdf.h1("6. Add a product")
    pdf.p("Stay on Inventory. Open the Products tab. Use Add product.")
    pdf.steps([
        "Name — required. Create product stays disabled until the name is filled.",
        "SKU — leave blank and the system assigns one, or type your own.",
        "Barcode — optional. 4 to 48 characters: letters, numbers, hyphen, dot, or underscore.",
        "Description — optional.",
        "Actual price — what the item costs you.",
        "Selling price — what you charge.",
        "Weight and size — optional, in kilograms and centimetres.",
        "Category, Brand, and Unit — choose what you created. Brand and unit can stay blank.",
        "Tax class — standard-rated, zero-rated, or exempt.",
        "Tax rate — choose a rate, or leave blank to use the category or company default.",
        "Click Create product.",
    ])
    pdf.p(
        "The new row appears in the product table. Quantity on hand is still zero until you "
        "post opening stock or receive a purchase."
    )

    pdf.h1("7. Picture, barcode, and deactivate")
    pdf.steps([
        "At the top of Inventory, open Selected product and choose the item.",
        "Add gallery image — PNG, JPEG, WebP, or GIF, up to 5 pictures. The first one is primary. Use Set primary to change it.",
        "Type or scan a barcode, or click Generate, then Print to make a shelf label.",
        "Change cost, selling price, reorder level, category, or tax, then click Save product.",
        "Click Deactivate to hide the item from sales, purchasing, and POS. Stock tools still work. Click Activate to bring it back.",
    ])
    pdf.p("Lookup tab: scan a barcode or search name or SKU, then Select. That loads warehouse stock.")

    pdf.h1("8. Put quantity on hand")
    pdf.p("Use Opening stock when the shop already holds goods on the first day. Select the product first.")
    pdf.steps([
        "Selected product — choose the item. Posting refuses to run if this is blank.",
        "Open the Opening stock tab.",
        "Warehouse — choose the store warehouse, or leave blank.",
        "Quantity, and unit if it is not the product default.",
        "Unit cost — blank uses the product actual price.",
        "Batch number, manufacturing date, and expiry — only for items you track that way. Dates are YYYY-MM-DD.",
        "Reference — leave blank to take the next opening-stock number.",
        "Click Post opening stock.",
    ])
    pdf.p(
        "Later: Stock counts to count the shelf, then complete the count. Adjust for a one-off correction. "
        "Stock Out for goods that leave without a sale. Transfers move quantity between warehouses. "
        "Do not create a second product to fix a count."
    )

    pdf.h1("9. Many products at once")
    pdf.steps([
        "Create categories, brands, and units first. The file cannot invent them.",
        "Inventory, Import tab, Download CSV template.",
        "Fill one row per product. Do not rename the columns.",
        "Choose the file, click Validate, and fix every error row.",
        "When validation can be committed, click Import valid rows. One bad row blocks the file.",
        "Export products CSV any time you want a copy of the catalog.",
    ])

    pdf.h1("10. Customer, then a sale")
    pdf.p("Open Sales.")
    pdf.steps([
        "Under Customer, enter the name and the other fields you use, then click Add customer.",
        "Under Create sale, choose the product, quantity, and price. Tax fills from the product when a rate exists.",
        "Click Create invoice. That saves a draft. Stock does not move yet.",
        "On the draft row, click Post. Stock decreases when the invoice is posted.",
        "Record what was paid. Any unpaid balance stays on Credit until a later payment is recorded.",
    ])
    pdf.p(
        "A quotation is only a price offer. It does not reduce stock. A return is created under "
        "Create return. Stock comes back when that return is posted, not while it is a draft. "
        "Do not delete a paid document to clear a balance."
    )

    pdf.h1("11. Sell at the till")
    pdf.steps([
        "Open POS. Confirm the store at the top of the screen.",
        "Enter opening cash if asked, then click Open shift.",
        "Search or scan a product and add it to the cart. Change quantity or a line discount if needed.",
        "Payment: Cash, Card, Digital wallet, or Credit. Split tender is cash plus card.",
        "Click Charge · Complete sale. Print or share the receipt from the success screen.",
        "At the end of the day click Shift report, then Close shift.",
        "Sign out. Do not leave a shift open on a shared till.",
    ])

    pdf.h1("12. Buy stock from a supplier")
    pdf.p("Open Purchasing. The tabs are Requests, Orders, GRNs, Invoices, and Returns.")
    pdf.steps([
        "On Orders, Quick add supplier: name, optional code, and type (Registered, Trade, Manufacturer, or Service). Click Add.",
        "Create purchase order: select the supplier and the product, quantity, and cost. Click Create draft PO.",
        "Send or approve the order with the actions on that row when your process requires it.",
        "When goods arrive, open the order and click Post GRN (accept / reject), or Receive all accepted. Stock increases by the accepted quantity.",
        "On Invoices, create the supplier bill from the goods receipt, or a manual invoice, and record the payment. Partial payments are allowed.",
        "On Returns, create a purchase return when goods go back. Stock decreases when that return is completed.",
    ])

    pdf.h1("13. Expenses")
    pdf.steps([
        "Open Expenses. Add a category first if you need one, such as rent, utilities, or transport.",
        "Enter the amount, category, date, and payment method: Cash, Bank transfer, Card, or Cheque.",
        "Click Submit expense.",
        "If approval is on, a manager approves it before it is final.",
    ])

    pdf.h1("14. Tax, accounting, and stores")
    pdf.p("Open Tax before you price products, if the company charges tax.")
    pdf.steps([
        "Under Create rate, enter a name, for example VAT, and the percent.",
        "Type: VAT, GST, Sales tax, or Custom.",
        "Exclusive adds tax on top of the price. Inclusive means the price already includes tax.",
        "Click Add rate. Then set that rate on the product or category so invoices calculate it. Do not type tax by hand if a rate exists.",
    ])
    pdf.p(
        "Accounting holds the chart of accounts, journals, transfers between accounts, and statements "
        "such as trial balance, where your package includes them. Ribdigi ERP records how the customer "
        "paid. It does not receive, hold, or settle funds."
    )
    pdf.p("Open Multi-Store when the company has more than one shop. The package limits how many stores you can create.")
    pdf.steps([
        "Create a branch if you group shops, then a department if you use departments.",
        "New store: code, name, address, and phone. Click Create store.",
        "New warehouse for that store if stock sits in a named warehouse. Click Create warehouse.",
        "Use the store switcher in the top bar before you sell, count, or receive.",
        "Move goods with a transfer. Do not edit the product quantity by hand to fake a move.",
    ])

    pdf.h1("15. Reports")
    pdf.p("Reports & Analytics summarizes sales, profit, stock, tax, and other lists for the current company and, where selected, the current store. Open a report, set the date range, then export or print if the button is shown. Reports never include another company's data.")

    pdf.h1("16. Users and roles")
    pdf.p("Company administrators use Users to add staff.")
    pdf.steps([
        "Create the user with name, email, and a strong password.",
        "Role — company admin, store manager, sales officer, inventory officer, accountant, cashier, or a custom role. Cashiers usually see Dashboard, Inventory, POS, Sales, Notifications, and Security.",
        "Limit the user to a branch or store when they should not see the whole company.",
        "Deactivate a user who leaves. Do not share one login among several people.",
    ])
    pdf.p(
        "Hiding a menu is not the only control. The server also checks permission. If an action "
        "is refused, ask an administrator to grant the role. Do not share the company admin password."
    )

    pdf.h1("17. Security and preferences")
    pdf.bullets([
        "Change your password from Security if you were given a temporary one.",
        "Turn on authenticator (TOTP) or a passkey if your company requires it. Save backup codes in a private place.",
        "Review active sessions and sign out devices you do not recognize.",
        "Use the theme control for light or dark mode. It applies only to you.",
        "The app signs you out after a period of inactivity set by the company.",
    ])

    pdf.h1("18. Notifications, audit, and backups")
    pdf.bullets([
        "Notifications lists low stock, payment due dates, and similar alerts. Mark items read when you have acted.",
        "Audit is a history of important changes. It is for review, not for editing transactions.",
        "Backup, when your role includes it, downloads an encrypted company backup. Store that file safely. It is not a substitute for your host's database backups.",
    ])

    pdf.h1("19. A normal selling day")
    pdf.steps([
        "Sign in with your company workspace, email, and password.",
        "Confirm the store at the top of the screen.",
        "Check Dashboard for low stock or amounts due.",
        "Sell on POS or Sales.",
        "Receive supplier deliveries in Purchasing if goods arrive.",
        "Record expenses paid from the till or bank.",
        "Close the POS shift.",
        "Sign out.",
    ])

    pdf.h1("20. Jobs, integrations, and AI")
    pdf.bullets([
        "Jobs shows scheduled work such as low-stock alerts, payment-due reminders, and backups. Company administrators can review status. Starting a job is limited to the platform owner.",
        "Integrations is for API keys and webhooks that connect Ribdigi ERP to another system. Only a company administrator should create a key. Treat the key like a password.",
        "AI Assistant, when your package includes it, can answer questions about your company data and draft notes. Check the numbers in the original report or invoice before you act on a draft.",
    ])

    pdf.h1("21. If something does not work")
    pdf.bullets([
        "Workspace, email, or password rejected: confirm the company slug and that the user is active.",
        "You return to the sign-in page: sign in again. If it repeats, ask an administrator to check your account.",
        "A button is missing: your role or package does not include that module.",
        "Stock did not change: the invoice, return, or goods receipt is still a draft. Click Post. A quotation does not move stock.",
        "Create product is disabled: the name is empty. Opening stock says select a product: choose Selected product first.",
        "Import is blocked: Validate still has error rows, or a category, brand, or unit in the file does not exist.",
        "Totals look wrong: check quantity, discount, and tax rate on each line before saving.",
    ])
    pdf.p("For product questions, contact your company administrator or Ribdigi House.")

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0,
        5,
        "This guide describes the customer workspace. It does not replace your company procedures "
        "or tax advice. Menus you do not see are switched off for your role or subscription.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(OUT)


if __name__ == "__main__":
    build()
