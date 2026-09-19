#!/usr/bin/env python3
"""Build the customer-facing Ribdigi ERP user guide PDF."""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "guides" / "RIBDIGI-ERP-Customer-User-Guide.pdf"
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
        "This guide is for company users: owners, managers, cashiers, and staff who sign in "
        "to their company workspace. It explains everyday work in Ribdigi ERP. Your company "
        "administrator controls which menus you can see."
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

    pdf.h1("5. Inventory")
    pdf.p("Inventory is the product catalog and stock.")
    pdf.h2("Set up products")
    pdf.steps([
        "Create categories, brands, and units first if you use them.",
        "Add a product with a name, SKU or barcode, cost price, and selling price.",
        "Set reorder level so low-stock alerts can fire.",
        "Add an expiry date for items that expire.",
        "Upload a product image if you use one at the till.",
    ])
    pdf.h2("Stock")
    pdf.bullets([
        "A purchase receipt increases stock.",
        "A sale or POS checkout decreases stock.",
        "A sales return puts stock back when the return is completed.",
        "A purchase return reduces stock when goods go back to the supplier.",
        "Stock adjustment corrects counts after a count.",
        "Stock transfer moves quantity from one store or warehouse to another. The source goes down and the destination goes up together.",
    ])
    pdf.p("Use low-stock, out-of-stock, and expiring filters before you reorder.")

    pdf.h1("6. Sales")
    pdf.p("Sales covers quotations, invoices, and sales returns.")
    pdf.steps([
        "Choose the customer, or leave a walk-in sale if your process allows it.",
        "Add products, quantities, discounts, and tax.",
        "Check the subtotal, tax, and grand total before you save.",
        "Record the amount paid. Any unpaid balance stays as credit until a later payment is recorded.",
        "Save. Stock for sold items decreases.",
        "For a return, open Sales return, select the sale, and complete the return so stock is restored.",
    ])
    pdf.p(
        "A quotation is a price offer. It does not reduce stock until you convert it to a sale. "
        "Credit sales leave an outstanding balance until later payments are recorded."
    )

    pdf.h1("7. Point of Sale")
    pdf.p("POS is the till for counter sales.")
    pdf.steps([
        "Open POS and confirm the correct store and shift.",
        "Search or scan a product and add it to the cart.",
        "Adjust quantity or a line discount if needed.",
        "Take payment as Cash, Card, Digital wallet, or Credit. You can split a payment between cash and card.",
        "Complete the sale. A receipt can be printed or shared from the success screen.",
        "Close the shift and review the shift report at the end of the day.",
    ])
    pdf.p("Do not leave a shift open on a shared device after you log out.")

    pdf.h1("8. Purchasing")
    pdf.p("Purchasing covers suppliers, purchase orders, goods receipts, and purchase returns.")
    pdf.steps([
        "Create or select a supplier.",
        "Raise a purchase order with items, quantities, and cost.",
        "When goods arrive, receive them. Stock increases by the received quantity.",
        "Record the supplier payment against the purchase. Partial payments are allowed.",
        "If you send goods back, complete a purchase return so stock decreases.",
    ])

    pdf.h1("9. Customers, suppliers, and credit")
    pdf.p(
        "Keep customer and supplier records so invoices and purchases stay tied to the right party. "
        "Credit shows who still owes you and what you still owe suppliers. Record a payment against "
        "the open document. The outstanding balance falls by the amount you enter. Do not delete a "
        "paid document to 'clear' a balance."
    )

    pdf.h1("10. Expenses")
    pdf.p(
        "Expenses records money the company spends that is not a product purchase: rent, utilities, "
        "transport, and similar costs. Enter the amount, category, date, and payment method: Cash, Bank transfer, Card, or Cheque. "
        "Recurring expenses can be scheduled by an administrator. Expenses appear on the dashboard "
        "and in reports."
    )

    pdf.h1("11. Accounting and tax")
    pdf.p(
        "Accounting holds the chart of accounts, journals, money transfers between accounts, and "
        "statements such as trial balance, balance sheet, and cash flow, according to your package. "
        "Tax holds tax rates used on sales and purchases. Set the rate on the product or category "
        "so invoices calculate tax for you. Do not type tax by hand if a rate already exists."
    )
    pdf.p(
        "Ribdigi ERP records payment information. It does not receive, hold, or settle customer "
        "funds. Cash, card, digital wallet, bank transfer, and credit are records of how the customer paid your business."
    )

    pdf.h1("12. Multi-store")
    pdf.p(
        "Multi-Store is for companies with more than one shop or warehouse. Create the store, "
        "assign staff who may sell there, and switch store in the top bar before selling or counting "
        "stock. A transfer is the correct way to move goods between stores."
    )

    pdf.h1("13. Reports")
    pdf.p("Reports & Analytics summarizes sales, profit, stock, tax, and other lists for the current company and, where selected, the current store. Open a report, set the date range, then export or print if the button is shown. Reports never include another company's data.")

    pdf.h1("14. Users and roles")
    pdf.p("Company administrators use Users to add staff.")
    pdf.steps([
        "Create the user with name, email, and a strong password.",
        "Assign a role such as company admin, store manager, cashier, or a custom role.",
        "Limit the user to a branch or store when they should not see the whole company.",
        "Deactivate a user who leaves. Do not share one login among several people.",
    ])
    pdf.p(
        "Hiding a menu is not the only control. The server also checks permission. If an action "
        "is refused, ask an administrator to grant the role. Do not share the company admin password."
    )

    pdf.h1("15. Security and preferences")
    pdf.bullets([
        "Change your password from Security if you were given a temporary one.",
        "Turn on authenticator (TOTP) or a passkey if your company requires it. Save backup codes in a private place.",
        "Review active sessions and sign out devices you do not recognize.",
        "Use the theme control for light or dark mode. It applies only to you.",
        "The app signs you out after a period of inactivity set by the company.",
    ])

    pdf.h1("16. Notifications, audit, and backups")
    pdf.bullets([
        "Notifications lists low stock, payment due dates, and similar alerts. Mark items read when you have acted.",
        "Audit is a history of important changes. It is for review, not for editing transactions.",
        "Backup, when your role includes it, downloads an encrypted company backup. Store that file safely. It is not a substitute for your host's database backups.",
    ])

    pdf.h1("17. A normal selling day")
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

    pdf.h1("18. Jobs, integrations, and AI")
    pdf.bullets([
        "Jobs shows scheduled work such as low-stock alerts, payment-due reminders, and backups. Company administrators can review status. Starting a job is limited to the platform owner.",
        "Integrations is for API keys and webhooks that connect Ribdigi ERP to another system. Only a company administrator should create a key. Treat the key like a password.",
        "AI Assistant, when your package includes it, can answer questions about your company data and draft notes. Check the numbers in the original report or invoice before you act on a draft.",
    ])

    pdf.h1("19. If something does not work")
    pdf.bullets([
        "Workspace, email, or password rejected: confirm the company slug and that the user is active.",
        "You return to the sign-in page: sign in again. If it repeats, ask an administrator to check your account.",
        "A button is missing: your role or package does not include that module.",
        "Stock did not change: confirm the document was saved, not left as a draft or quotation.",
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
