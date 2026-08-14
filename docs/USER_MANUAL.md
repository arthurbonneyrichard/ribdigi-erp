# RIBDIGI BUSINESS ERP — User Manual

> **Version:** 1.0 (MVP)  
> **Last Updated:** August 2026  
> **For:** End Users (Store Managers, Cashiers, Sales Officers, Inventory Officers, Accountants, Company Admins)

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Your Dashboard](#2-your-dashboard)
3. [Inventory Management](#3-inventory-management)
4. [Sales](#4-sales)
5. [Point of Sale (POS)](#5-point-of-sale-pos)
6. [Purchasing](#6-purchasing)
7. [Expense Management](#7-expense-management)
8. [Basic Accounting](#8-basic-accounting)
9. [Credit Management](#9-credit-management)
10. [Tax Management](#10-tax-management)
11. [Multi-Store Management](#11-multi-store-management)
12. [Reports](#12-reports)
13. [Notifications](#13-notifications)
14. [AI Business Assistant](#14-ai-business-assistant)
15. [System Settings](#15-system-settings)
16. [Troubleshooting & FAQs](#16-troubleshooting--faqs)

---

## 1. Getting Started

### 1.1 Logging In

1. Open your browser and navigate to your company's RIBDIGI ERP URL (e.g., `https://yourcompany.ribdigi.com`).
2. Enter your **Email Address** and **Password**.
3. Click **Sign In**.
4. If Two-Factor Authentication (2FA) is enabled, enter the 6-digit code from your authenticator app.

> **Tip:** Bookmark your login page for quick access. If you forget your password, click **Forgot Password?** and follow the email reset instructions.

### 1.2 First-Time Setup (For Company Admins)

If you're setting up RIBDIGI for the first time:

1. **Complete Company Profile**
   - Go to **Settings → Company Information**
   - Upload your company logo
   - Fill in legal name, address, phone, tax ID
   - Select your **Industry** (Retail, Pharmacy, Restaurant, Bakery, Wholesale, or Manufacturing)
   - Set your **Base Currency** and **Time Zone**
   - Define your **Fiscal Year Start Date**

2. **Set Up Branches & Stores**
   - Navigate to **Admin → Branches** and add each business location
   - Go to **Admin → Stores** to create retail/service points
   - Go to **Admin → Warehouses** to set up storage locations

3. **Configure Tax**
   - Go to **Settings → Tax Configuration**
   - Add your default tax rate (e.g., VAT 15%)
   - Set whether prices are tax-inclusive or tax-exclusive

4. **Add Users**
   - Go to **Admin → Users → Create User**
   - Add your team members and assign roles
   - Each role comes with pre-configured permissions

5. **Set Up Chart of Accounts**
   - Go to **Accounting → Chart of Accounts**
   - Review the pre-loaded accounts based on your industry
   - Adjust opening balances if migrating mid-year

#### Getting started checklist

New tenants see a **Getting started** banner at the top of the main workspace (not on the platform owner console). It tracks five steps with a progress bar:

1. Setup company profile → Company
2. Add products → Inventory
3. Create a supplier → Purchasing
4. Stock on hand → Inventory
5. Make first sale → Sales

Steps auto-complete when the system detects matching data. Company admins can **Skip** / **Undo skip** individual steps. The banner is **Dismiss**ible at ≥80% progress (skips count). After dismiss, admins can **Restore checklist** until progress reaches 100%.

### 1.3 Understanding the Interface

#### Main Navigation Sidebar
```
┌─────────────────────────────┐
│  [Logo] RIBDIGI ERP         │
├─────────────────────────────┤
│  📊 Dashboard               │
│  📦 Inventory               │
│  🛒 Sales                   │
│  🖥️  POS                    │
│  🛍️  Purchasing             │
│  💰 Accounting              │
│  💳 Expenses                │
│  🏪 Multi-Store             │
│  📈 Reports                 │
│  🤖 AI Assistant            │
│  🔔 Notifications           │
│  ⚙️  Settings               │
│  🛡️  Admin (if permitted)   │
└─────────────────────────────┘
```

#### Top Bar
- **Store Selector:** Switch the active store context in the header (persisted per tenant). Seeds POS, Sales, Reports, Tax, and Expenses store pickers; choose **All stores** for company-wide views when multiple stores exist.
- **Notification Bell:** View alerts and messages
- **Profile Menu:** Access your profile, change password, or log out
- Theme toggle (light/dark)
#### Common UI Patterns
| Element | Action |
|---------|--------|
| **+ New** button | Creates a new record (product, invoice, order, etc.) |
| **Filters** | Narrow down lists by date, status, category, etc. |
| **Export** | Download data as CSV, Excel, or PDF |
| **Print** | Generate a print-friendly version |
| **Actions (⋮)** | Edit, delete, view, or perform special actions on a row |
| **Save Draft** | Save incomplete work to finish later |
| **Submit** | Finalize and process the record |

---

## 2. Your Dashboard

The Dashboard is your command center — a real-time snapshot of your business health.

### 2.1 KPI Cards (Top Row)

| Card | What It Shows | Click to View |
|------|--------------|---------------|
| **Total Sales** | Revenue today/this month | Sales report detail |
| **Total Purchases** | Purchase value today/this month | Purchase report |
| **Total Expenses** | Expenses today/this month | Expense report |
| **Customers** | Total active customers | Customer list |
| **Suppliers** | Total active suppliers | Supplier list |
| **Products** | Total products in catalog | Product list |

> **Color Indicators:** Green = trending up vs. last period | Red = trending down

### 2.2 Inventory Alerts

- **Low Stock:** Number of products below reorder level. Click to see the list and generate purchase suggestions.
- **Out of Stock:** Products with zero quantity. Immediate action recommended.
- **Expiring Soon:** (Pharmacy/Food) Products nearing expiry date.

### 2.3 Sales Visualization

- **Recent Sales:** Last 10 transactions with customer, amount, and status
- **Top Products:** Best-selling products by revenue and quantity
- **Daily Revenue Chart:** 30-day trend line
- **Monthly Revenue Chart:** 12-month bar chart for year-over-year comparison

### 2.4 Notifications Panel

Click the **🔔 bell icon** to see:
- Low stock alerts
- New orders received
- Purchase goods received
- Payment due reminders
- Credit limit warnings
- System announcements

> **Mark as Read:** Click the checkmark or "Mark All as Read" to clear notifications.

---

## 3. Inventory Management

### 3.1 Managing Products

#### Adding a New Product

1. Go to **Inventory → Products → + New Product**
2. Fill in the product form:

| Field | Description | Example |
|-------|-------------|---------|
| **Product Name** | Display name | "Paracetamol 500mg" |
| **SKU** | Unique stock code | "MED-PARA-500" |
| **Barcode** | Scan code (EAN/UPC) | "8901234567890" |
| **Category** | Product classification | "Pain Relief / Tablets" |
| **Brand** | Manufacturer brand | "HealthCare Pharma" |
| **Unit** | Measurement unit | "Strip", "Box", "Kg" |
| **Cost Price** | Purchase cost per unit | $2.50 |
| **Selling Price** | Retail price per unit | $4.00 |
| **Tax Rate** | Applicable tax | "VAT 15%" |
| **Description** | Optional details | "For mild to moderate pain" |

3. **For Product Variants** (e.g., sizes, colors):
   - Enable **"Has Variants"**
   - Add variant options (Size: Small, Medium, Large)
   - Each variant gets its own SKU and barcode

4. **For Pharmacy/Food:**
   - Enter **Batch Number**
   - Set **Manufacturing Date** and **Expiry Date**
   - System will auto-alert before expiry

5. Upload product images (up to 5 images; first image is primary)
6. Click **Save**

> **Bulk Import:** Use **Inventory → Products → Import** to upload hundreds of products via CSV template.

#### Editing a Product
1. Go to **Inventory → Products**
2. Search for the product using the search bar or filters
3. Click the **Actions (⋮)** menu → **Edit**
4. Update fields and click **Save**

> **Note:** Changing cost price does not affect existing stock valuation. New stock will use the updated cost.

#### Managing Categories & Brands
- **Categories:** Go to **Inventory → Categories** to create a hierarchical tree (e.g., Electronics → Mobile Phones → Smartphones)
- **Brands:** Go to **Inventory → Brands** to add manufacturer brands with logos

### 3.2 Stock Operations

#### Stock In (Receiving Goods)

Use this when:
- Goods arrive from a supplier (linked to PO/GRN)
- Stock is returned by a customer
- Found during stock count

**Steps:**
1. Go to **Inventory → Stock In → + New Stock In**
2. Select **Reference Type**: Purchase Order, Transfer, or Adjustment
3. Select the **Warehouse** receiving the stock
4. Add products:
   - Scan barcode or search by name/SKU
   - Enter quantity received
   - Enter batch and expiry (if applicable)
5. Click **Submit**
6. Stock is immediately updated

#### Stock Out (Issuing Goods)

Use this when:
- Goods are sold (usually auto-generated from sales invoice)
- Goods are transferred to another warehouse
- Goods are damaged or expired

**Steps:**
1. Go to **Inventory → Stock Out → + New Stock Out**
2. Select **Reference Type**: Sales, Transfer, Damage, Expiry
3. Select the **Warehouse**
4. Add products and quantities
5. Add reason for stock out
6. Click **Submit**

#### Stock Adjustment

Use this to correct discrepancies between physical and system stock:

1. Go to **Inventory → Stock Adjustment → + New Adjustment**
2. Select **Warehouse**
3. Add products with:
   - **System Quantity** (auto-filled, read-only)
   - **Physical Quantity** (what you counted)
   - **Difference** (auto-calculated)
   - **Reason**: Damage, Theft, Found, Lost, Expiry, Other
4. Attach supporting documents if needed
5. Click **Submit**

> **Important:** Stock adjustments affect your accounting. Large adjustments may require manager approval.

#### Stock Transfer (Between Warehouses)

1. Go to **Inventory → Stock Transfer → + New Transfer**
2. Select **Source Warehouse** and **Destination Warehouse**
3. Add products and quantities
4. Click **Request Transfer**
5. The destination warehouse manager will receive a notification to **Approve & Receive**
6. Once received, stock moves automatically

#### Stock Count (Physical Inventory)

1. Go to **Inventory → Stock Count → + New Count**
2. Select **Warehouse**
3. Choose count method:
   - **Full Count:** All products
   - **Partial Count:** Specific categories or products
   - **Cycle Count:** Random sample
4. Enter actual quantities for each product
5. System highlights variances
6. Click **Generate Adjustment** to create stock adjustment for variances

### 3.3 Managing Warehouses

1. Go to **Inventory → Warehouses**
2. View stock levels per warehouse
3. Click a warehouse to see:
   - Total products
   - Stock value
   - Low stock items
   - Recent movements

### 3.4 Low Stock Alerts

1. Go to **Inventory → Products**
2. For each product, set:
   - **Minimum Stock Level:** Absolute minimum before emergency reorder
   - **Reorder Level:** Trigger point for normal reorder
   - **Reorder Quantity:** Suggested quantity to order
3. When stock hits reorder level, you'll receive:
   - Dashboard alert
   - Email notification (if configured)
   - SMS alert (if configured)
4. Click **Generate Purchase Suggestion** to auto-create a Purchase Request

---

## 4. Sales

### 4.1 Managing Customers

#### Adding a Customer

1. Go to **Sales → Customers → + New Customer**
2. Fill in:
   - **Name** (required)
   - **Phone** (required)
   - **Email**
   - **Address**
   - **Customer Group** (Retail, Wholesale, VIP — affects pricing)
   - **Credit Limit** (0 for cash-only customers)
3. Click **Save**

#### Customer Groups

- Go to **Sales → Customer Groups**
- Create groups with different pricing tiers:
  - **Retail:** Standard selling price
  - **Wholesale:** 10% discount
  - **VIP:** 15% discount
- Assign customers to groups for automatic pricing

#### Customer Balance

- View real-time outstanding balance on the customer profile
- See full transaction history: invoices, payments, returns, credits

### 4.2 Creating a Quotation

1. Go to **Sales → Quotations → + New Quotation**
2. Select **Customer** (or create new)
3. Add products:
   - Search by name/SKU/barcode
   - Quantity and unit price auto-filled (editable)
   - Apply **Line discount** and optional **Header discount** on Create sale (tax before line discount)
4. Set **Validity Period** (e.g., 7 days)
5. Add notes/terms
6. Click **Save** (draft) or **Send** (email to customer)
7. Print or download as PDF

> **Follow-up:** The system reminds you 1 day before quotation expiry.

### 4.3 Creating a Sales Order

1. Go to **Sales → Sales Orders → + New Order**
   - Or convert from a quotation: Open quotation → **Convert to Order**
2. Select **Customer**
3. Add products and quantities (optional **Line discount** / **Header discount** on Create sale)
4. Set **Expected Delivery Date**
5. Click **Confirm Order**
6. System reserves inventory

**Order Statuses:**
| Status | Meaning |
|--------|---------|
| Draft | Being prepared |
| Confirmed | Customer approved; inventory reserved |
| Processing | Being packed/prepared |
| Shipped | Dispatched to customer |
| Delivered | Received by customer |
| Cancelled | Order cancelled |

### 4.4 Creating a Sales Invoice

1. Go to **Sales → Invoices → + New Invoice**
   - Or convert from sales order: Open order → **Convert to Invoice**
2. Select **Customer**
3. Add products (auto-filled from order if converting)
4. Review:
   - Subtotal
   - Tax (auto-calculated)
   - Line + header **Discount** (Create sale fields; detail KPI)
   - **Total Amount**
5. Select **Payment Method**:
   - **Cash:** Immediate payment
   - **Card:** Record card transaction
   - **Credit:** Customer pays later (checks credit limit)
   - **Digital Wallet:** Record wallet payment
6. Click **Save & Print** or **Save & Email**

> **Credit Sales:** If customer has insufficient credit limit, system blocks the sale. Company Admin can override.

#### Invoice Actions
- **Print:** Thermal receipt or A4 invoice
- **Email:** Send PDF to customer automatically
- **Duplicate:** Create copy for recurring billing
- **Cancel:** Void invoice (requires reason; creates reversal entries)

### 4.5 Processing a Sales Return

1. Go to **Sales → Sales Returns → + New Return**
2. Select the **Original Invoice**
3. Products auto-populate; select which items are being returned
4. Enter return quantity and reason:
   - Damaged
   - Wrong item
   - Quality issue
   - Customer changed mind
   - Expired
5. Choose handling:
   - **Restock:** Add back to inventory
   - **Discard:** Do not restock (damaged/expired)
6. Click **Process Return**
7. System generates a **Credit Note** and updates customer balance

---

## 5. Point of Sale (POS)

The POS module is designed for fast, intuitive checkout at retail counters.

### 5.1 Opening Your Shift

**Before you can make any sales, you must open a shift:**

1. Go to **POS → Open Shift**
2. Enter your **Opening Cash Float** (cash in drawer at start)
3. Click **Open Shift**
4. System records: Cashier name, timestamp, opening amount

> **Tip:** Count your cash carefully. The closing reconciliation depends on accurate opening numbers.

### 5.2 Making a Sale

#### Method 1: Barcode Scanner
1. Scan the product barcode
2. Product automatically adds to cart with quantity 1
3. Scan again to increase quantity

#### Method 2: Product Search
1. Type product name, SKU, or barcode in the search box
2. Click the product from suggestions
3. Or browse by category tiles

#### Managing the Cart
- **+ / −:** Adjust quantity
- **🗑️:** Remove item
- **% Discount:** Apply percentage discount to item
- **$ Discount:** Apply fixed discount to item
- **Clear Cart:** Remove all items

#### Applying Cart-Level Discounts
1. Click **Discount** button
2. Choose:
   - **Percentage:** e.g., 10% off entire cart
   - **Fixed Amount:** e.g., $5 off entire cart
3. Enter reason for discount (required for audit)

#### Selecting a Customer
1. Click **Customer** button
2. Search by name or phone
3. Select customer (or leave as "Walk-in Customer")
4. If customer has a credit limit, it displays here

#### Processing Payment

1. Review the cart total
2. Click **Pay**
3. Select payment method(s):

| Method | How It Works |
|--------|-------------|
| **Cash** | Enter amount received; system calculates change |
| **Card** | Enter card last 4 digits; record reference number |
| **Digital Wallet** | Select wallet (Apple Pay, Google Pay, etc.); record transaction ID |
| **Credit** | Available only for registered customers within credit limit |
| **Split Payment** | Combine multiple methods (e.g., $20 cash + $30 card) |

4. Click **Complete Sale**
5. Receipt prints automatically (if printer connected)
6. Digital receipt can be emailed/SMSed to customer

> **Keyboard Shortcuts:**
> - `F2` — Search product
> - `F4` — Select customer
> - `F9` — Apply discount
> - `F12` — Complete payment
> - `ESC` — Cancel current action

### 5.3 Handling Returns at POS

1. Go to **POS → Return**
2. Scan or search the original receipt/invoice
3. Select items to return
4. Choose refund method (cash, card, store credit)
5. Process return

### 5.4 Closing Your Shift

**At end of day (or shift change):**

1. Go to **POS → Close Shift**
2. Count your actual cash in drawer
3. Enter **Closing Cash Amount**
4. System shows:
   - Opening float
   - Total cash sales
   - Total refunds
   - Expected cash = Opening + Sales − Refunds
   - **Variance** = Expected − Actual
5. Add notes if variance exists
6. Click **Close Shift**
7. System generates **Shift Report** with:
   - Total sales, returns, discounts
   - Payment method breakdown
   - Cash reconciliation
   - Top products sold

> **Variance Alert:** If variance exceeds threshold, manager notification is sent automatically.

---

## 6. Purchasing

### 6.1 Managing Suppliers

#### Adding a Supplier

1. Go to **Purchasing → Suppliers → + New Supplier**
2. Fill in:
   - **Name** (required)
   - **Code** (auto-generated or manual)
   - **Type** (Manufacturer, Distributor, Wholesaler)
   - **Contact Details:** Phone, email, address
   - **Payment Terms:** Credit period (e.g., Net 30)
   - **Tax ID**
3. Add multiple contacts (sales rep, accounts payable contact)
4. Click **Save**

#### Supplier Balance
- View real-time outstanding payable
- See purchase history, return history, payment history
- Generate supplier statement anytime

### 6.2 Purchase Request (PR)

**When to use:** You need to request approval before buying goods.

1. Go to **Purchasing → Purchase Requests → + New PR**
2. Select **Requesting Department** and **Required Date**
3. Add products with requested quantities
4. Add preferred supplier (optional)
5. Add justification notes
6. Click **Submit for Approval**

**Approval Workflow:**
```
Inventory Officer creates PR
        ↓
Store Manager reviews & approves/rejects
        ↓
(If approved) → Converted to Purchase Order
```

> **Track Status:** Go to **Purchasing → Purchase Requests** to see all PRs and their status.

### 6.3 Purchase Order (PO)

**When to use:** You're ready to formally order from a supplier.

1. Go to **Purchasing → Purchase Orders → + New PO**
   - Or convert from approved PR
2. Select **Supplier**
3. Add products:
   - Search by name/SKU
   - Enter quantity and negotiated unit price
   - System auto-calculates tax and total
4. Set **Expected Delivery Date**
5. Add delivery address and terms
6. Click **Save** (draft) or **Send to Supplier**

**PO Statuses:**
| Status | Meaning |
|--------|---------|
| Draft | Being prepared |
| Sent | Emailed to supplier |
| Partially Received | Some items arrived |
| Fully Received | All items arrived |
| Cancelled | Order cancelled |

> **Print/Email:** Click **Print** for physical copy or **Email** to send PDF directly to supplier.

### 6.4 Goods Received Note (GRN)

**When goods arrive from supplier:**

1. Go to **Purchasing → GRN → + New GRN**
2. Select the **Purchase Order** being received
3. PO details auto-populate
4. For each product:
   - Enter **Received Quantity** (may be less than ordered)
   - Enter **Batch Number** and **Expiry Date** (if applicable)
   - Mark items as **Accepted** or **Rejected** (with reason)
5. Click **Submit GRN**
6. System:
   - Updates inventory
   - Updates PO status
   - Notifies accountant to create purchase invoice

> **Partial Receipts:** If only some items arrive, create GRN for received items. The PO remains "Partially Received" until fully fulfilled.

### 6.5 Purchase Invoice

1. Go to **Purchasing → Purchase Invoices → + New Invoice**
   - Or convert from GRN
2. Select **Supplier**
3. Line items auto-populate from GRN
4. Enter:
   - **Invoice Number** (from supplier's bill)
   - **Invoice Date**
   - **Due Date**
5. Attach supplier's PDF invoice (optional but recommended)
6. Click **Save**
7. System updates:
   - Accounts Payable
   - Supplier balance

### 6.6 Purchase Return

**When returning goods to supplier:**

1. Go to **Purchasing → Purchase Returns → + New Return**
2. Select the **Original PO/GRN**
3. Select products and return quantities
4. Choose reason: Damaged, Wrong Item, Quality Issue, Expired
5. System:
   - Deducts from inventory
   - Generates debit note
   - Updates supplier balance

---

## 7. Expense Management

### 7.1 Recording an Expense

1. Go to **Expenses → + New Expense**
2. Fill in:
   - **Date** (default: today)
   - **Category** (Rent, Utilities, Salaries, Transportation, etc.)
   - **Amount**
   - **Payment Method** (Cash, Bank Transfer, Card, Cheque)
   - **Payee**
   - **Reference Number** (receipt number, cheque number)
   - **Description**
   - **Branch/Department** (for multi-location tracking)
3. **Attach Receipt:** Upload photo or PDF of receipt
4. Click **Submit**
5. After upload, use **Preview** (image/PDF modal) or **Download**; **OCR** can suggest amount/date/payee

> **Categories:** On Expenses → Category budgets, set monthly budgets / GL, and **Deactivate** obsolete categories (history kept). Inactive categories are hidden from new expense / recurring pickers until **Activate** again.

> **OCR Tip:** The AI Document Assistant can auto-extract amount, date, and vendor from receipt images. Expenses also has per-row **OCR** + **Preview**.

### 7.2 Expense Approval

If the expense exceeds your company's approval threshold:

1. Expense status becomes **Pending Approval**
2. Approver (usually Store Manager or Company Admin) receives notification
3. Approver reviews — use **Edit** on pending (or rejected) rows to fix amount/payee/description/reference before deciding — then clicks **Approve** or **Reject** with comments
4. Approved expenses are posted to accounting automatically

### 7.3 Recurring Expenses

For regular payments like rent or subscriptions:

1. Go to **Expenses** and open the **Recurring expenses** card
2. Set:
   - **Frequency:** Daily, Weekly, Monthly, Yearly
   - **Amount**, **Category**, optional payee / branch / department
3. Click **Create schedule** — the system stores `next_run_at` and Celery generates due expenses automatically
4. Use **Generate due now** to run the same job immediately (generated expenses use EXP numbering)
5. **Skip next** advances `next_run_at` by one period without creating an expense (e.g. skip a holiday cycle)
6. **Deactivate** / **Activate** a schedule from the list when you need to pause it

> Advance notifications (category `recurring_expense_due`) fire about one day before `next_run_at` via Notifications → Scan due / Celery. To change one occurrence’s amount/payee: **Generate due**, then **Edit** that pending expense before approve. To change the schedule’s default amount/payee for future runs: **Edit schedule** on the Recurring card (does not rewrite past expenses).

### 7.4 Expense Reports

Go to **Reports → Expense Summary** to see:
- Total expenses by period
- Breakdown by category
- Budget vs. actual comparison
- Top expense categories

---

## 8. Basic Accounting

### 8.1 Chart of Accounts (COA)

The COA is the backbone of your accounting. RIBDIGI comes pre-loaded with an industry-appropriate COA.

**Account Types:**
| Type | Code Range | Examples |
|------|-----------|----------|
| **Assets** | 1000–1999 | Cash, Bank, Inventory, Receivables |
| **Liabilities** | 2000–2999 | Payables, Loans, Tax Payable |
| **Equity** | 3000–3999 | Capital, Retained Earnings |
| **Income** | 4000–4999 | Sales Revenue, Interest Income |
| **Expenses** | 5000–5999 | Rent, Salaries, Utilities, COGS |

**To add a new account:**
1. Go to **Accounting → Chart of Accounts**
2. Click **+ New Account**
3. Select account type and enter code, name, description
4. Set opening balance if applicable
5. Click **Save**

> **System Accounts** (marked with 🔒) are auto-managed and cannot be deleted.

### 8.2 Journal Entries

For adjustments, accruals, and corrections:

1. Go to **Accounting → Journal Entries → + New Entry**
2. Enter **Date** and **Reference**
3. Add lines:
   - Select **Account**
   - Enter **Debit** or **Credit** amount
   - Add description per line
4. Ensure **Total Debits = Total Credits** (system validates)
5. Attach supporting document
6. Click **Post**

> **Important:** Once posted, journal entries can only be unposted within the same fiscal period. After period close, they are immutable.

### 8.3 Cash & Bank Accounts

#### Viewing Balances
- Go to **Accounting → Cash Accounts** or **Bank Accounts**
- See current balance, recent transactions, and reconciliation status

#### Recording Transactions
- **Deposit:** Cash → Bank
- **Withdrawal:** Bank → Cash
- **Transfer:** Bank A → Bank B
- **Cheque:** Record issued, deposited, or bounced cheques

#### Bank Reconciliation
1. Go to **Accounting → Bank Accounts → Reconcile**
2. System shows:
   - **System Balance:** Per your books
   - **Statement Balance:** Per bank statement (you enter this)
3. Match transactions:
   - Check off transactions that appear on bank statement
   - Add missing transactions (bank fees, interest)
4. Click **Complete Reconciliation**
5. **Difference** should be zero

### 8.4 Accounts Receivable (AR)

1. Go to **Accounting → Accounts Receivable**
2. See all outstanding customer invoices
3. **Aging Report:** View how long invoices have been unpaid
   - 0–30 days (Current)
   - 31–60 days
   - 61–90 days
   - 90+ days (Overdue)
4. Click **Record Payment** to:
   - Select invoice(s) to pay
   - Enter amount, date, method
   - System updates customer balance

### 8.5 Accounts Payable (AP)

1. Go to **Accounting → Accounts Payable**
2. See all outstanding supplier bills
3. **Aging Report:** View upcoming and overdue payments
4. Click **Record Payment** to:
   - Select bill(s) to pay
   - Enter amount, date, method
   - System updates supplier balance

### 8.6 Financial Reports

#### Profit & Loss (P&L)
- **Go to:** Accounting → Reports → Profit & Loss
- **Shows:** Revenue − Cost of Goods Sold = Gross Profit; Gross Profit − Expenses = Net Profit
- **Filters:** Date range, branch, store
- **Export:** PDF, Excel

#### Cash Flow Statement
- **Go to:** Accounting → Reports → Cash Flow
- **Shows:** Operating, Investing, and Financing activities
- Identifies cash inflows and outflows

#### Trial Balance
- **Go to:** Accounting → Reports → Trial Balance
- **Shows:** All accounts with debit and credit balances
- **Validation:** Total Debits must equal Total Credits
- Used for period-end verification

---

## 9. Credit Management

### 9.1 Customer Credit

#### Setting Credit Limits
1. Go to **Sales → Customers**
2. Open a customer profile
3. Set **Credit Limit** (e.g., $5,000)
4. Set **Credit Period** (e.g., Net 30 days)

#### Monitoring Outstanding Balances
- Customer profile shows real-time outstanding amount
- **Credit Utilization:** (Outstanding / Limit) × 100
- System blocks new credit sales if limit is exceeded

#### Recording Payments
1. Go to **Sales → Customers → [Customer] → Record Payment**
2. Or go to **Accounting → Accounts Receivable → Record Payment**
3. Enter:
   - Amount
   - Date
   - Payment method
   - Allocate to specific invoices or auto-allocate (oldest first)
4. Click **Save**

#### Customer Statement
1. Go to **Sales → Customers → [Customer] → Statement**
2. Select date range
3. System generates statement with:
   - Opening balance
   - All invoices, payments, returns, credits
   - Closing balance
4. Print or email to customer

### 9.2 Supplier Credit

- View outstanding bills per supplier at **Purchasing → Suppliers**
- **Payment Schedule:** See upcoming due dates
- Record payments via **Accounting → Accounts Payable**
- Generate supplier statements for reconciliation

---

## 10. Tax Management

### 10.1 Configuring Tax Rates

1. Go to **Settings → Tax Configuration**
2. Click **+ New Tax Rate**
3. Enter:
   - **Name:** e.g., "Standard VAT"
   - **Rate:** e.g., 15%
   - **Type:** VAT, GST, Sales Tax
   - **Applicability:** All products or specific categories
4. Set as **Default** if applicable

### 10.2 Tax on Transactions

Tax is automatically calculated on:
- Sales invoices
- Purchase invoices
- POS transactions

**Tax-Inclusive vs. Tax-Exclusive:**
- **Inclusive:** Price entered includes tax; system shows tax breakdown
- **Exclusive:** Tax added on top of price

> Configure this in **Settings → Tax Configuration → Default Pricing Method**

### 10.3 Tax Reports

1. Go to **Reports → Tax Reports**
2. Select **Period** (Monthly, Quarterly, Annually)
3. System shows:
   - **Output Tax:** Tax collected on sales
   - **Input Tax:** Tax paid on purchases
   - **Net Tax Payable:** Output − Input
   - Or **Net Tax Refundable:** If input > output
4. Export in format required by your tax authority

---

## 11. Multi-Store Management

### 11.1 Switching Between Stores

Use the **Store Selector** in the top navigation bar to switch context. Your dashboard, inventory, and sales data will update to reflect the selected store.

### 11.2 Inter-Store Transfers

1. Go to **Multi-Store → Transfers → + New Transfer**
2. Select **From Store** and **To Store**
3. Add products and quantities
4. Click **Request Transfer**
5. The receiving store manager gets a notification
6. They review and click **Receive** (or reject with reason)
7. Stock updates automatically at both locations

### 11.3 Consolidated vs. Store-Specific Reports

- **Store-Specific:** Select a single store in the report filters
- **Consolidated:** Select "All Stores" to see combined data
- **Comparison:** Some reports allow side-by-side store comparison

---

## 12. Reports

### 12.1 Accessing Reports

Go to **Reports** from the main sidebar. Reports are organized by category:

### 12.2 Sales Reports

| Report | What It Shows | Best For |
|--------|-------------|----------|
| **Daily Sales** | Sales per day with invoice count, revenue, tax | Daily reconciliation |
| **Monthly Sales** | Monthly aggregation with trend | Monthly reviews |
| **Product Sales** | Product-wise quantity and revenue | Identifying top/bottom performers |
| **Customer Sales** | Sales per customer | Customer analysis |
| **Salesperson Performance** | Sales by team member | Commission calculation |

**How to use:**
1. Select report type
2. Set date range
3. Apply filters (store, category, customer group)
4. Click **Generate**
5. View on screen, print, or export to Excel/PDF

### 12.3 Inventory Reports

| Report | What It Shows |
|--------|--------------|
| **Stock Balance** | Current stock per product per warehouse |
| **Low Stock** | Products below reorder level |
| **Stock Movement** | All in/out/transfer/adjustment history |
| **Stock Valuation** | Inventory value by costing method |
| **Expiry Report** | Products nearing expiry (pharmacy/food) |

### 12.4 Purchase Reports

| Report | What It Shows |
|--------|--------------|
| **Purchase Summary** | Total purchases by period |
| **Supplier Purchases** | Volume and value per supplier |
| **Pending Orders** | POs not yet received |
| **Purchase Return Summary** | Returns by reason and supplier |

### 12.5 Expense Reports

- Expense summary by category and period
- Budget vs. actual comparison
- Top expense categories

### 12.6 Financial Reports

- **Profit & Loss:** Business profitability
- **Cash Flow:** Cash movement analysis
- **Trial Balance:** Account balance verification
- **Balance Sheet:** Assets, liabilities, and equity snapshot

### 12.7 Scheduling Reports

1. Generate any report
2. Click **Schedule**
3. Set frequency (Daily, Weekly, Monthly)
4. Add email recipients
5. System auto-sends the report at scheduled times

---

## 13. Notifications

### 13.1 Viewing Notifications

Click the **🔔 bell icon** in the top navigation bar.

**Notification Categories:**
| Icon | Type | Example |
|------|------|---------|
| 📦 | Inventory | "Product XYZ is below reorder level" |
| 🛒 | Sales | "New sales order #SO-1024 received" |
| 🛍️ | Purchase | "GRN received for PO #PO-558" |
| 💰 | Payment | "Invoice #INV-2045 is overdue by 5 days" |
| ⚠️ | Credit | "Customer ABC has reached 90% of credit limit" |
| 🔔 | System | "Scheduled backup completed" |

### 13.2 Managing Notification Preferences

1. Go to **Settings → Notifications**
2. For each notification type, choose channels:
   - **Dashboard:** In-app notification
   - **Email:** Send to registered email
   - **SMS:** Send to registered phone
3. Click **Save Preferences**

> **Note:** SMS notifications may incur additional charges based on your subscription plan.

---

## 14. AI Business Assistant

### 14.1 AI ERP Chat Assistant

Access the AI assistant via the **🤖 floating button** on the bottom-right of any screen.

**What you can ask:**

| Type | Example Queries |
|------|----------------|
| **Data Queries** | "What were my total sales last month?"<br>"Show me low stock items"<br>"Who is my top customer?" |
| **Reports** | "Generate a monthly sales report"<br>"Show me profit and loss for Q2" |
| **Actions** | "Create a purchase request for 100 units of Product X"<br>"Send a payment reminder to Customer Y" |
| **Insights** | "Why did sales drop this week?"<br>"What products should I restock?" |

**Tips for best results:**
- Be specific with dates and product names
- Use natural language — no special syntax needed
- The assistant respects your role permissions

### 14.2 AI Dashboard Insights

On your dashboard, look for **💡 Insight Cards** that highlight:
- Unusual sales patterns (spikes or drops)
- Inventory recommendations
- Expense anomalies
- Customer behavior changes

Click **"View Details"** on any insight card to see the full analysis.

### 14.3 AI Low Stock Prediction

Instead of waiting for stock to hit reorder level, the AI predicts stockouts **7–14 days in advance** based on:
- Historical sales velocity
- Seasonal trends
- Lead time from suppliers

Go to **AI → Inventory predictions** to see at-risk SKUs (14-day window), then **Create draft PR(s)** for one-click draft purchase requests:
- Predicted stockout timing (`days_to_stockout`)
- Recommended order quantity
- Confidence score
- Draft PRs appear under **Purchasing → Requests** (requires purchasing write permission)

> Reports → Inventory also has threshold-based low-stock suggestions with a separate draft-PR action.

### 14.4 AI Document Assistant

When uploading receipts or invoices:
1. Go to **Expenses → + New Expense**
2. Upload receipt image
3. AI auto-extracts:
   - Amount
   - Date
   - Vendor name
   - Expense category suggestion
4. Review and confirm extracted data
5. Click **Submit**

---

## 15. System Settings

### 15.1 Company Information

Go to **Settings → Company Information** to update:
- Company name, logo, address
- Tax registration number
- Contact details
- Fiscal year settings

### 15.2 Formatting Preferences

Go to **Settings → Formatting** to set:
- **Date Format:** DD/MM/YYYY, MM/DD/YYYY, or YYYY-MM-DD
- **Number Format:** Decimal and thousand separators
- **Time Format:** 12-hour or 24-hour

### 15.3 Invoice & Receipt Templates

Go to **Settings → Templates** to customize:
- Invoice numbering prefix (e.g., "INV-2026-")
- Receipt template (thermal or A4)
- Header/footer text
- Terms and conditions
- Logo placement

### 15.4 Email Settings

Go to **Settings → Email** to configure:
- SMTP server for sending emails
- Default sender name and email
- Email templates for invoices, quotations, and notifications

---

## 16. Troubleshooting & FAQs

### 16.1 Common Issues

#### "I can't log in"
- ✅ Check Caps Lock is off
- ✅ Ensure you're using the correct company URL
- ✅ Try resetting your password via "Forgot Password"
- ✅ Contact your Company Admin if account is deactivated

#### "Product not showing in POS search"
- ✅ Check the product is marked as **Active**
- ✅ Verify the product has stock in the selected store/warehouse
- ✅ Confirm your user has POS permissions

#### "Invoice won't save — says 'Credit Limit Exceeded'"
- ✅ Customer has reached their credit limit
- ✅ Options: Request payment, increase credit limit (Company Admin), or split payment (part cash, part credit)

#### "Stock shows negative"
- ✅ Check if **Allow Negative Stock** is enabled in settings
- ✅ If disabled, you cannot sell more than available stock
- ✅ Perform a stock adjustment or stock in to correct

#### "Tax calculation looks wrong"
- ✅ Check if product is set to **Tax-Inclusive** or **Tax-Exclusive**
- ✅ Verify the tax rate assigned to the product category
- ✅ Check Settings → Tax Configuration for default rules

#### "Report is blank or missing data"
- ✅ Verify date range includes transactions
- ✅ Check store/branch filter isn't excluding data
- ✅ Ensure you have permission to view that report

### 16.2 Keyboard Shortcuts (POS)

| Key | Action |
|-----|--------|
| `F2` | Search product |
| `F4` | Select customer |
| `F9` | Apply discount |
| `F12` | Complete payment |
| `ESC` | Cancel/clear |
| `+` | Increase quantity |
| `−` | Decrease quantity |

### 16.3 Getting Help

| Issue Type | Contact |
|------------|---------|
| **Login/Access Issues** | Your Company Admin |
| **Feature How-To** | This User Manual or In-App Help (?) |
| **Bug Report** | Support via Settings → Help & Support |
| **Billing/Subscription** | RIBDIGI Support Team |
| **Technical Issues** | RIBDIGI Support with screenshot and steps to reproduce |

### 16.4 Data Export

You can export your data anytime:
- **Products:** Inventory → Products → Export
- **Customers:** Sales → Customers → Export
- **Sales:** Sales → Invoices → Export
- **Reports:** Any report → Export to Excel/PDF

### 16.5 Mobile App

Download the RIBDIGI mobile app for:
- Viewing dashboard on the go
- Approving expenses and purchase requests
- Checking inventory levels
- Monitoring sales in real-time
- Receiving push notifications

> **Download:** Available on App Store and Google Play. Search "RIBDIGI ERP".

---

<p align="center">
  <strong>RIBDIGI BUSINESS ERP</strong><br>
  <em>One ERP Platform. Unlimited Business.</em><br><br>
  © 2026 RIBDIGI. All rights reserved.
</p>
