# RIBDIGI BUSINESS ERP — Administrator Manual

> **Version:** 1.0 (MVP)  
> **Last Updated:** August 2026  
> **For:** Super Admins, Company Admins, and System Administrators  
> **Classification:** Internal — Authorized Personnel Only

---

## Table of Contents

1. [Introduction & Role Definitions](#1-introduction--role-definitions)
2. [Accessing the Admin Panel](#2-accessing-the-admin-panel)
3. [Multi-Tenant Management](#3-multi-tenant-management)
4. [System Administration](#4-system-administration)
5. [User Management](#5-user-management)
6. [Role & Permission Configuration](#6-role--permission-configuration)
7. [Backup & Recovery](#7-backup--recovery)
8. [Audit Logs & Compliance](#8-audit-logs--compliance)
9. [System Settings](#9-system-settings)
10. [Security Administration](#10-security-administration)
11. [Maintenance & Monitoring](#11-maintenance--monitoring)
12. [Troubleshooting](#12-troubleshooting)
13. [Appendix](#13-appendix)

---

## 1. Introduction & Role Definitions

### 1.1 Purpose of This Manual

This Administrator Manual provides comprehensive guidance for managing the RIBDIGI BUSINESS ERP platform at the tenant and system levels. It covers tenant lifecycle management, user provisioning, security configuration, backup operations, audit compliance, and system maintenance.

### 1.2 Administrator Roles Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPER ADMIN                               │
│  (Platform-Level — RIBDIGI Internal Staff Only)             │
│  • Manage all tenants                                        │
│  • System-wide configuration                                 │
│  • Infrastructure monitoring                                 │
│  • Global security policies                                  │
├─────────────────────────────────────────────────────────────┤
│                   COMPANY ADMIN                              │
│  (Tenant-Level — Business Owner / IT Manager)               │
│  • Manage company settings                                   │
│  • User and role management                                  │
│  • Branch/store/warehouse setup                              │
│  • Subscription and billing                                  │
│  • Backup and restore operations                             │
│  • Audit log access                                          │
├─────────────────────────────────────────────────────────────┤
│                  STORE MANAGER                               │
│  (Location-Level — Store/Branch Manager)                    │
│  • Store-specific settings                                   │
│  • Staff assignment                                          │
│  • Local inventory and sales oversight                       │
│  • Shift and cash reconciliation                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Prerequisites

Before performing administrative tasks, ensure you have:
- Valid administrator credentials (Super Admin or Company Admin)
- Two-Factor Authentication (2FA) enabled (mandatory for admin accounts)
- Understanding of your company's organizational structure (branches, departments, stores)
- Familiarity with basic accounting principles (for COA and tax setup)

---

## 2. Accessing the Admin Panel

### 2.1 Login

1. Navigate to your RIBDIGI ERP URL: `https://[tenant].ribdigi.com/admin`
   - **Super Admin:** Use `https://admin.ribdigi.com` (platform console)
   - **Company Admin:** Use your tenant-specific URL
2. Enter your **Email** and **Password**
3. Enter your **2FA Code** from your authenticator app
4. Click **Sign In**

### 2.2 Admin Dashboard

Upon login, the Admin Dashboard displays:

```
┌─────────────────────────────────────────────────────────────┐
│  [RIBDIGI Logo]     Admin Console     [Notifications] [👤]  │
├──────────────┬──────────────────────────────────────────────┤
│  NAVIGATION  │           MAIN CONTENT AREA                  │
│              │                                              │
│  🏢 Tenant   │  ┌─────────────┐ ┌─────────────┐           │
│     Mgmt     │  │ Active      │ │ Suspended   │           │
│              │  │ Tenants: 42 │ │ Tenants: 3  │           │
│  👥 Users    │  └─────────────┘ └─────────────┘           │
│              │                                              │
│  🏪 Stores   │  ┌─────────────┐ ┌─────────────┐           │
│              │  │ Total Users │ │ System      │           │
│  🏭 Branches │  │     1,247   │ │ Health: ✅  │           │
│              │  └─────────────┘ └─────────────┘           │
│  🏭 Warehouse│                                              │
│              │  Recent Activity                             │
│  ⚙️ Settings │  • Tenant "ABC Pharma" created — 2 min ago │
│              │  • Backup completed — 15 min ago            │
│  🛡️ Security │  • User login failure alert — 1 hr ago    │
│              │                                              │
│  📊 Audit    │                                              │
│     Logs     │                                              │
│              │                                              │
│  💾 Backup   │                                              │
│              │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

### 2.3 Navigation Quick Reference

| Menu Item | Access Level | Description |
|-----------|-------------|-------------|
| **Tenant Management** | Super Admin | Create, monitor, and manage all tenants |
| **Company Setup** | Company Admin | Configure company profile and structure |
| **User Management** | Company Admin | Add, edit, deactivate users; manage roles |
| **Roles & Permissions** | Company Admin | Define and assign access control |
| **System Settings** | Company Admin | Global configuration (currency, format, email) |
| **Backup & Recovery** | Company Admin | Manual and scheduled backup operations |
| **Audit Logs** | Company Admin | View and export activity logs |
| **Security Center** | Company Admin | Session management, 2FA enforcement, password policies |

---

## 3. Multi-Tenant Management

> **⚠️ Super Admin Only**

### 3.1 Understanding Multi-Tenancy

RIBDIGI uses a **database-per-tenant** isolation model. Each tenant (company) receives:
- Isolated PostgreSQL database/schema
- Independent file storage bucket
- Separate encryption keys
- Dedicated configuration space

This ensures complete data separation between businesses.

### 3.2 Creating a New Tenant

1. Go to **Tenant Management → Create Tenant**
2. Fill in the **Tenant Registration Form**:

| Field | Required | Description |
|-------|----------|-------------|
| **Company Name** | Yes | Legal business name |
| **Subdomain** | Yes | Unique URL identifier (e.g., `abcpharma` → `abcpharma.ribdigi.com`) |
| **Admin Email** | Yes | Primary administrator email |
| **Industry** | Yes | Retail, Pharmacy, Restaurant, Bakery, Wholesale, Manufacturing |
| **Currency** | Yes | Base operating currency |
| **Time Zone** | Yes | Local time zone for timestamps |
| **Fiscal Year Start** | Yes | Month and day (e.g., January 1 or April 1) |
| **Subscription Plan** | Yes | Starter / Professional / Enterprise / Trial |
| **Company Address** | No | Full business address |
| **Tax ID** | No | Business tax registration number |

3. Click **Create Tenant**
4. System performs:
   - Subdomain availability check
   - Database/schema creation
   - Seed data injection (COA, tax rates, units, categories based on industry)
   - Admin user creation with temporary password
   - Welcome email sent to admin email

5. **Confirmation Screen** shows:
   - Tenant ID
   - Database name
   - Admin login credentials (password must be changed on first login)
   - API endpoint URL

### 3.3 Monitoring Tenant Status

Go to **Tenant Management → Tenant List** to view:

| Column | Description |
|--------|-------------|
| **Tenant ID** | Unique system identifier |
| **Company Name** | Business name |
| **Subdomain** | Access URL |
| **Industry** | Selected vertical |
| **Plan** | Current subscription tier |
| **Status** | Trial / Active / Suspended / Pending |
| **Users** | Current user count / plan limit |
| **Storage** | Used / allocated storage |
| **Created** | Registration date |
| **Last Active** | Most recent admin login |

**Status Definitions:**
| Status | Meaning | Action Required |
|--------|---------|-----------------|
| **Trial** | 14-day evaluation period | Monitor conversion; send reminders |
| **Active** | Paid subscription in good standing | None |
| **Suspended** | Payment failed or violation | Contact tenant; 30-day grace period |
| **Pending** | Registration incomplete | Send activation reminder |

### 3.4 Managing Tenant Lifecycle

#### Upgrading/Downgrading Plans
1. Open tenant profile from Tenant List
2. Click **Change Plan**
3. Select new plan
4. System adjusts:
   - User limits
   - Storage quotas
   - Feature availability
   - Billing cycle
5. **Proration:** If mid-cycle, system calculates prorated charge/credit

#### Suspending a Tenant
1. Open tenant profile
2. Click **Suspend**
3. Select reason:
   - Payment overdue
   - Terms of service violation
   - Admin request
   - Other
4. Set suspension type:
   - **Soft:** Read-only access (data viewable, no edits)
   - **Hard:** Complete access block (emergency only)
5. Add internal notes
6. Click **Confirm Suspension**

> **Effect:** Users see a suspension message on login. Data is preserved for 90 days before archival.

#### Reactivating a Tenant
1. Open suspended tenant profile
2. Click **Reactivate**
3. Confirm billing details if applicable
4. System restores full access immediately

#### Deleting a Tenant
> **⚠️ IRREVERSIBLE ACTION**

1. Open tenant profile
2. Click **Delete Tenant**
3. Complete the safety checklist:
   - [ ] Export all data
   - [ ] Notify tenant administrator
   - [ ] Confirm billing closure
   - [ ] Enter tenant name for confirmation
4. Click **Permanently Delete**
5. System:
   - Archives database to cold storage (retained 30 days)
   - Deletes active database
   - Releases storage resources
   - Removes DNS records
   - Sends deletion confirmation to Super Admin

### 3.5 Tenant Database Initialization

When a tenant is created, the system automatically seeds:

**Based on Industry Selection:**

| Industry | Pre-Loaded Data |
|----------|----------------|
| **Retail** | Product categories (Electronics, Clothing, Home), standard units, retail COA |
| **Pharmacy** | Drug categories (OTC, Prescription, Supplements), dosage units, pharmacy COA, expiry tracking fields |
| **Restaurant** | Food categories (Appetizers, Mains, Beverages), ingredient units, recipe fields, restaurant COA |
| **Bakery** | Product types (Breads, Pastries, Cakes), batch units, production BOM fields, bakery COA |
| **Wholesale** | Bulk categories, packaging units, wholesale pricing tiers, wholesale COA |
| **Manufacturing** | Raw material categories, production units, BOM structure, manufacturing COA |

**Universal Seed Data:**
- Default tax rate (configurable post-creation)
- Standard units of measure (Piece, Kg, Liter, Box, Carton, Dozen)
- Default expense categories (Rent, Utilities, Salaries, Transportation)
- Predefined roles (Company Admin, Store Manager, Sales Officer, Inventory Officer, Accountant, Cashier)
- Default receipt and invoice templates

---

## 4. System Administration

> **Company Admin Level**

### 4.1 Company Information Setup

1. Go to **Admin → Company Setup → Company Information**
2. Complete all fields:

| Field | Purpose | Example |
|-------|---------|---------|
| **Legal Name** | Official business name for invoices/reports | "ABC Pharmaceuticals Ltd." |
| **Trading Name** | DBA name if different | "ABC Pharmacy" |
| **Registration Number** | Business registration ID | "BR-2024-001234" |
| **Tax ID / VAT Number** | Tax authority identifier | "VAT-987654321" |
| **Phone** | Primary contact | "+1-555-0123" |
| **Email** | Official email | "admin@abcpharma.com" |
| **Website** | Business website | "www.abcpharma.com" |
| **Logo** | Displayed on invoices, receipts, reports | Upload PNG/JPG (max 2MB, 500×500px) |

3. **Addresses:**
   - **Registered Address:** Legal business address
   - **Billing Address:** For invoices to customers
   - **Shipping Address:** Default dispatch location
   - Add multiple addresses using **+ Add Address**

4. Click **Save Changes**

> **Tip:** A complete company profile ensures professional-looking invoices and compliance-ready reports.

### 4.2 Branch Management

Branches represent major business divisions (e.g., regional offices, distinct business units).

#### Creating a Branch
1. Go to **Admin → Company Setup → Branches**
2. Click **+ New Branch**
3. Fill in:
   - **Branch Code:** Unique identifier (e.g., "BR001", "NYC-EAST")
   - **Branch Name:** Display name (e.g., "New York East Branch")
   - **Manager:** Select from user list (must have Store Manager or higher role)
   - **Address:** Full address with GPS coordinates (optional)
   - **Phone & Email:** Branch-specific contact
   - **Status:** Active / Inactive
4. Click **Create Branch**

#### Branch Operations
- **Edit:** Update branch details or reassign manager
- **Deactivate:** Soft-disable branch (preserves historical data; prevents new transactions)
- **View:** See branch summary (stores, warehouses, staff count, revenue)

### 4.3 Store Management

Stores are retail/service points where sales and POS transactions occur.

#### Creating a Store
1. Go to **Admin → Company Setup → Stores**
2. Click **+ New Store**
3. Configure:

| Field | Description |
|-------|-------------|
| **Store Code** | Unique identifier (e.g., "ST-001") |
| **Store Name** | Display name (e.g., "Downtown Store") |
| **Branch** | Parent branch assignment |
| **Manager** | Assigned store manager |
| **Warehouse** | Default stock source |
| **Address** | Store location |
| **Operating Hours** | Opening/closing times per day |
| **POS Terminals** | Number of active POS stations |
| **Receipt Template** | Select thermal or A4 format |
| **Tax Rate** | Override default tax if location-specific |

4. Click **Create Store**

#### Store Configuration
- **POS Settings:** Enable/disable payment methods, set cash drawer thresholds, configure receipt footer message
- **Inventory:** Set store-specific reorder levels
- **Staff:** Assign cashiers and sales officers to this store

### 4.4 Warehouse Setup

Warehouses are storage locations for inventory.

#### Creating a Warehouse
1. Go to **Admin → Company Setup → Warehouses**
2. Click **+ New Warehouse**
3. Configure:

| Field | Description |
|-------|-------------|
| **Warehouse Code** | Unique ID (e.g., "WH-MAIN") |
| **Warehouse Name** | Display name |
| **Type** | Retail, Bulk, Cold Storage, Raw Material, Finished Goods |
| **Branch** | Associated branch |
| **Manager** | Warehouse/inventory officer |
| **Address** | Location |
| **Capacity** | Max storage (optional tracking) |
| **Temperature Control** | For cold storage (pharmacy/food) |

4. Click **Create Warehouse**

> **Warehouse Types:**
> - **Retail:** Small stock for immediate sales
> - **Bulk:** Large quantity storage
> - **Cold Storage:** Temperature-controlled (pharmacy, food)
> - **Raw Material:** Manufacturing inputs
> - **Finished Goods:** Manufacturing outputs

### 4.5 Department Setup

Departments organize users for reporting and approval workflows.

1. Go to **Admin → Company Setup → Departments**
2. Click **+ New Department**
3. Enter:
   - **Department Name** (e.g., "Sales", "Inventory", "Accounting")
   - **Department Code** (e.g., "DEPT-SALES")
   - **Head:** Department manager
   - **Parent Department:** For hierarchical structures (optional)
4. Click **Create**

**Use Cases:**
- Expense allocation by department
- Approval routing (e.g., department head approves expenses)
- Reporting filters (sales by department)

### 4.6 Currency Setup

For businesses operating in multiple currencies:

1. Go to **Admin → Company Setup → Currencies**
2. **Base Currency** is set during tenant creation (cannot be changed after transactions exist)
3. Click **+ Add Currency** to add foreign currencies:
   - Select currency from dropdown (USD, EUR, GBP, etc.)
   - Set **Exchange Rate** against base currency
   - Choose update method:
     - **Manual:** Admin updates rates
     - **Auto:** API integration with exchange rate provider (e.g., OpenExchangeRates)
4. Set **Effective Date** for rate

> **Transaction Currency:** Users can select currency during sales/purchase transactions. System auto-converts to base currency for reporting.

### 4.7 Language Configuration

1. Go to **Admin → Company Setup → Languages**
2. **Default Language:** Set for all users (MVP: English only)
3. **User-Level Override:** Individual users can set their preferred language in profile settings
4. **i18n Framework:** Ready for future language packs (Spanish, French, Arabic, Chinese, etc.)

### 4.8 Tax Configuration

Proper tax setup is critical for compliance.

#### Adding Tax Rates
1. Go to **Admin → Company Setup → Tax Configuration**
2. Click **+ New Tax Rate**
3. Configure:

| Field | Description | Example |
|-------|-------------|---------|
| **Tax Name** | Display name | "Standard VAT" |
| **Tax Code** | Short identifier | "VAT-15" |
| **Rate** | Percentage | 15% |
| **Type** | VAT, GST, Sales Tax, Service Tax | VAT |
| **Default** | Apply to new products automatically | Yes/No |
| **Compound** | Calculate tax on top of other taxes | No |
| **Inclusive/Exclusive** | Price includes or excludes tax | Exclusive |

4. **Product Category Mapping:**
   - Select which categories this tax applies to
   - Create exemptions (e.g., "Essential Goods — 0%")

5. Click **Save**

#### Tax Rules
- **Multiple Rates:** Support for standard, reduced, and zero-rated taxes
- **Compound Tax:** Tax calculated on subtotal + previous tax (e.g., GST + PST)
- **Reverse Charge:** For B2B transactions where buyer pays tax directly

> **⚠️ Warning:** Changing tax rates does not retroactively affect existing transactions. New rates apply to new invoices only.

---

## 5. User Management

### 5.1 Creating a New User

1. Go to **Admin → Users → Create User**
2. Fill in the user profile:

| Field | Required | Description |
|-------|----------|-------------|
| **Full Name** | Yes | First and last name |
| **Email** | Yes | Unique email; used as username |
| **Phone** | Yes | For SMS notifications and 2FA |
| **Role** | Yes | Predefined or custom role |
| **Branch** | No | Primary branch assignment |
| **Store** | No | Primary store (for cashiers, sales officers) |
| **Department** | No | Department affiliation |
| **Employee ID** | No | Internal employee reference |
| **Start Date** | No | Employment start date |

3. **Password Options:**
   - **Auto-generate:** System creates secure password; sent via email
   - **Manual:** Admin sets temporary password; user changes on first login

4. Click **Create User**
5. System sends welcome email with:
   - Login URL
   - Username (email)
   - Temporary password
   - First-time login instructions

### 5.2 Editing a User

1. Go to **Admin → Users**
2. Search or browse to find the user
3. Click **Actions (⋮) → Edit**
4. Update fields as needed:
   - Personal information
   - Role assignment
   - Branch/store reassignment
   - Department change
5. Click **Save**

> **Role Change Impact:** When changing a user's role, system immediately updates permissions. The user must refresh their browser or re-login for changes to take full effect.

### 5.3 Activating / Deactivating Users

**Deactivate** (recommended over delete):
1. Go to **Admin → Users**
2. Find user → **Actions (⋮) → Deactivate**
3. Select reason:
   - Employment terminated
   - Temporary leave
   - Role change pending
   - Security concern
4. Add notes
5. Confirm

**Effect of Deactivation:**
- User cannot log in
- All historical data preserved
- User removed from active staff lists
- Scheduled reports stop sending to this user

**Reactivate:**
1. Go to **Admin → Users**
2. Toggle **Show Inactive Users**
3. Find user → **Actions (⋮) → Activate**
4. User can log in again with existing credentials

### 5.4 Deleting a User

> **⚠️ CAUTION:** Deletion is permanent. Deactivation is preferred.

1. Go to **Admin → Users**
2. Find user → **Actions (⋮) → Delete**
3. Choose handling method:
   - **Reassign Records:** Transfer user's transactions to another user
   - **Preserve Records:** Keep transactions with "Deleted User" label
4. Enter confirmation text
5. Click **Permanently Delete**

### 5.5 Bulk User Import

For onboarding multiple users at once:

1. Go to **Admin → Users → Import**
2. Download the **CSV Template**
3. Fill in required columns:
   - `full_name`, `email`, `role`, `temporary_password`
   - Optional: `phone`
4. Upload CSV file
5. System validates:
   - Email uniqueness (file + tenant)
   - Role existence (system roles; `super_admin` blocked for non–super admins)
   - Password policy (upper, lower, number, symbol, min 8)
6. Review validation report
7. Click **Import valid rows** (all-or-nothing)
8. Verification emails dispatched for each created user

> **Template Download:** Available at **Users → Bulk import users → Download CSV template** (`GET /users/import/template`)

### 5.6 User Profile Management

Users can manage their own profiles, but admins can override:

**Admin-Editable Fields:**
- Role and permissions
- Branch/store assignments
- Account status (active/inactive)
- 2FA enforcement
- Session termination

**User-Editable Fields:**
- Profile photo
- Contact information
- Password
- Notification preferences
- Language preference

---

## 6. Role & Permission Configuration

### 6.1 Predefined Roles

RIBDIGI ships with 7 standard roles optimized for target industries:

| Role | Typical Users | Access Level |
|------|-------------|--------------|
| **Super Admin** | RIBDIGI platform staff | Full platform access |
| **Company Admin** | Business owner, CEO, CFO, IT manager | Full tenant access |
| **Store Manager** | Branch manager, retail manager | Store-level operations + reports |
| **Sales Officer** | Sales rep, account manager | Sales module + customer data |
| **Inventory Officer** | Warehouse manager, procurement | Inventory + purchasing |
| **Accountant** | Bookkeeper, finance officer | Accounting + financial reports |
| **Cashier** | Front-desk staff, POS operator | POS + basic sales view |

### 6.2 Permission Architecture

Permissions operate on three dimensions:

```
┌─────────────────────────────────────────────────────────────┐
│                    PERMISSION MATRIX                         │
├─────────────────────────────────────────────────────────────┤
│  1. MODULE PERMISSIONS                                       │
│     Can user access the Inventory module? Yes/No            │
├─────────────────────────────────────────────────────────────┤
│  2. MENU PERMISSIONS                                         │
│     Can user see "Stock Adjustment" submenu? Yes/No         │
├─────────────────────────────────────────────────────────────┤
│  3. RECORD PERMISSIONS                                       │
│     • Own Records: Only records created by the user         │
│     • Department Records: Records from user's department    │
│     • Branch Records: Records from user's branch            │
│     • All Records: Full visibility across tenant            │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Creating a Custom Role

When predefined roles don't fit your organization:

1. Go to **Admin → Roles & Permissions → Create Role**
2. Enter:
   - **Role Name** (e.g., "Assistant Manager")
   - **Description** (e.g., "Can manage inventory and approve expenses under $500")
   - **Base Role:** Copy permissions from an existing role (optional)

3. **Configure Module Permissions:**
   Toggle each module ON/OFF:
   - Dashboard, Inventory, Sales, POS, Purchasing, Accounting, Expenses, Reports, Settings

4. **Configure Menu Permissions:**
   For each enabled module, expand and toggle individual menu items:
   - Example: Inventory → Products (✅), Inventory → Stock Adjustment (✅), Inventory → Warehouses (❌)

5. **Configure Record Permissions:**
   For each module, set visibility:
   - **None:** Cannot view any records
   - **Own:** Only records they created
   - **Department:** Records from their department
   - **Branch:** Records from their branch
   - **All:** All records in the tenant

6. **Special Permissions:**
   - **Approve Expenses Up To:** $____ (set threshold)
   - **Override Credit Limit:** Yes/No
   - **Cancel Invoices:** Yes/No
   - **Modify System Settings:** Yes/No
   - **Export Data:** Yes/No
   - **View Audit Logs:** Own / Department / All

7. Click **Save Role**

### 6.4 Assigning Roles to Users

**Method 1: During User Creation**
- Select role from dropdown in the user creation form

**Method 2: Bulk Assignment**
1. Go to **Admin → Roles & Permissions → Assign Users**
2. Select role
3. Check users to assign
4. Click **Apply**

**Method 3: Individual Edit**
1. Go to **Admin → Users**
2. Edit user → Change role dropdown
3. Save

### 6.5 Permission Override (User-Level)

For exceptional cases where a user needs permissions different from their role:

1. Go to **Admin → Users → [User] → Permissions**
2. Toggle **"Override Role Permissions"**
3. Configure module, menu, and record permissions specifically for this user
4. Click **Save Override**

> **Best Practice:** Use role-level permissions for standard cases. User-level overrides should be rare and documented.

### 6.6 Permission Audit

1. Go to **Admin → Roles & Permissions → Audit**
2. View:
   - Which users have which roles
   - Which roles have which permissions
   - Users with permission overrides
   - Unused roles (no users assigned)
3. Export for compliance documentation

---

## 7. Backup & Recovery

### 7.1 Understanding Backup Architecture

RIBDIGI employs a multi-layer backup strategy:

```
┌─────────────────────────────────────────────────────────────┐
│                   BACKUP LAYERS                              │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Automated PostgreSQL WAL Archiving                 │
│           → Continuous point-in-time recovery                │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Daily Automated Full Backups                       │
│           → Complete tenant database + files                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Manual On-Demand Backups                           │
│           → Admin-triggered full snapshots                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Cross-Region Replication                           │
│           → Disaster recovery in secondary region            │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Performing a Manual Backup

1. Go to **Admin → Backup & Recovery → Manual Backup**
2. Select **Backup Scope:**
   - **Full Tenant:** Database + files + configurations
   - **Database Only:** Just the PostgreSQL data
   - **Files Only:** Uploaded documents, images, receipts

3. Add **Backup Label** (e.g., "Pre-Year-End-Close-2026")
4. Add **Description** (optional but recommended)
5. Click **Start Backup**
6. Monitor progress:
   - **Preparing:** Gathering data
     **Exporting:** Writing to archive
   - **Encrypting:** AES-256 encryption
   - **Uploading:** Transferring to S3 storage
   - **Completed:** Backup ready

7. **Backup Details** shown upon completion:
   - Backup ID
   - Timestamp
   - Size
   - Checksum (SHA-256)
   - Download link (valid 24 hours)

> **Storage:** Manual backups count against your storage quota. Monitor usage at **Admin → Backup & Recovery → Storage Usage**.

### 7.3 Configuring Scheduled Backups

1. Go to **Admin → Backup & Recovery → Scheduled Backups**
2. Toggle **Enable Scheduled Backups**
3. Configure schedule:

| Option | Description | Recommendation |
|--------|-------------|----------------|
| **Frequency** | How often to run | Daily for active businesses |
| **Time** | Hour:Minute (UTC) | During low-activity hours (2:00 AM) |
| **Day** | For weekly backups | Sunday |
| **Scope** | Full / Database / Files | Full |

4. Set **Retention Policy:**
   - **Keep Last N Backups:** e.g., 30 (1 month of daily backups)
   - **Keep Monthly Backups:** e.g., 12 (1 year of month-end backups)
   - **Keep Yearly Backups:** e.g., 7 (7 years for compliance)

5. **Notification:**
   - Email on success (optional)
   - Email on failure (recommended)
   - Alert if backup size differs >20% from average (anomaly detection)

6. Click **Save Schedule**

### 7.4 Restoring from Backup

> **⚠️ WARNING:** Restore operations overwrite current data. Perform during maintenance windows.

#### Restore to Same Tenant (Disaster Recovery)

1. Go to **Admin → Backup & Recovery → Restore**
2. Select **Restore Type:** "Restore to Current Tenant"
3. Choose backup source:
   - **From Backup List:** Select from available backups
   - **From Upload:** Upload external backup file (must be valid RIBDIGI backup)

4. Select **Restore Point:**
   - **Full Backup:** Restore to backup timestamp
   - **Point-in-Time:** Specify exact date/time (uses WAL archiving)

5. Review **Impact Assessment:**
   - Data modified after restore point will be lost
   - Active users will be logged out
   - POS operations must halt

6. Check **Pre-Restore Actions:**
   - [ ] Notify all users
   - [ ] Close all POS shifts
   - [ ] Pause scheduled jobs
   - [ ] Create fresh backup of current state (safety net)

7. Enter confirmation text: `"I understand this will overwrite current data"`
8. Click **Begin Restore**
9. Monitor progress:
   - Downloading backup archive
   - Verifying integrity (checksum)
   - Stopping active connections
   - Restoring database
   - Restoring files
   - Rebuilding indexes
   - Verification

10. **Post-Restore:**
    - System sends completion notification
    - Users can log back in
    - Verify critical data (last transaction, inventory levels)

#### Restore to New Tenant (Testing/Clone)

1. Go to **Admin → Backup & Recovery → Restore**
2. Select **Restore Type:** "Restore to New Tenant"
3. Enter new tenant details (subdomain, admin email)
4. Select backup file
5. Click **Create Clone**
6. System creates new tenant with backup data
7. Use for:
   - Testing upgrades
   - Training environments
   - Data analysis without affecting production

### 7.5 Backup Monitoring

Go to **Admin → Backup & Recovery → History** to view:

| Column | Description |
|--------|-------------|
| **Backup ID** | Unique identifier |
| **Type** | Manual / Scheduled |
| **Scope** | Full / Database / Files |
| **Started** | Timestamp |
| **Duration** | Time taken |
| **Size** | Archive size |
| **Status** | Success / Failed / In Progress |
| **Integrity** | Checksum verification result |

**Failed Backup Troubleshooting:**
- **Storage Full:** Free up space or upgrade plan
- **Database Lock:** Retry during low-activity period
- **Network Timeout:** Check connectivity; retry
- **Encryption Error:** Contact RIBDIGI Support

---

## 8. Audit Logs & Compliance

### 8.1 Understanding Audit Logging

RIBDIGI maintains immutable audit trails for:
- **Security Events:** Login attempts, password changes, 2FA events, session management
- **Data Changes:** Product create/update/delete, price changes, stock adjustments
- **Financial Events:** Invoice creation, payment recording, journal entries
- **User Management:** Role changes, permission updates, user activation/deactivation
- **System Events:** Backup operations, settings changes, tenant status changes

### 8.2 Viewing Audit Logs

1. Go to **Admin → Audit Logs**
2. **Filter Options:**

| Filter | Options |
|--------|---------|
| **Date Range** | Custom start/end dates |
| **User** | Specific user or all users |
| **Module** | Inventory, Sales, Purchasing, Accounting, Users, System |
| **Action Type** | Create, Update, Delete, Login, Logout, Export, Print |
| **Severity** | Info, Warning, Critical |
| **IP Address** | Filter by source IP |
| **Status** | Success, Failed |

3. **Log Entry Details:**
   Click any log entry to see:
   - Timestamp (with millisecond precision)
   - User identity
   - Action performed
   - Module and record affected
   - Before/after values (for updates)
   - IP address and user agent
   - Session ID

### 8.3 Exporting Audit Logs

1. Apply desired filters
2. Click **Export**
3. Select format:
   - **CSV:** For spreadsheet analysis
   - **PDF:** For compliance documentation
   - **JSON:** For SIEM integration
4. Select range:
   - Current filtered results
   - Full history (may be large)
5. Click **Download**

> **Retention:** Audit logs are retained for 7 years (financial records) or 2 years (operational logs) per compliance settings. Exports should be stored securely.

### 8.4 Compliance Reporting

**For Tax Audits:**
1. Go to **Admin → Audit Logs**
2. Filter: Module = Accounting, Date Range = fiscal year
3. Export as PDF with digital signature
4. Include:
   - All journal entries
   - Invoice modifications
   - Payment recordings
   - Tax configuration changes

**For Security Audits:**
1. Filter: Action Type = Login/Logout/Permission Change
2. Export failed login attempts
3. Export permission escalation events
4. Include session anomaly reports

### 8.5 Audit Log Integrity

RIBDIGI ensures tamper-evident logging:
- **Append-Only:** Logs cannot be modified or deleted through the UI
- **Cryptographic Hashing:** Each log entry includes a hash chain linking to previous entries
- **Immutable Storage:** Write-once storage backend for audit data
- **Access Control:** Only Company Admin and Super Admin can view audit logs

> **⚠️ Legal Hold:** In case of legal proceedings, contact RIBDIGI Support to place a legal hold on audit data, preventing automated archival deletion.

---

## 9. System Settings

### 9.1 Company Information

See Section 4.1 for detailed company profile setup.

**Quick Update Path:** Settings → Company Information

### 9.2 Regional Formatting

1. Go to **Settings → Formatting**
2. Configure:

| Setting | Options | Impact |
|---------|---------|--------|
| **Date Format** | DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD | Display across all screens and reports |
| **Time Format** | 12-hour (AM/PM), 24-hour | Timestamp display |
| **Number Format** | 1,234.56 or 1.234,56 | Decimal/thousand separators |
| **Currency Symbol Position** | Before ($100) or After (100$) | Invoice and receipt display |
| **Negative Number Format** | (100) or -100 | Financial reports |

3. Click **Save**

> **Effect:** Changes apply immediately to all users. Existing reports are not retroactively reformatted.

### 9.3 Email Configuration

Proper email setup ensures notifications, invoices, and reports reach recipients.

1. Go to **Settings → Email**
2. **SMTP Configuration:**

| Field | Description | Example |
|-------|-------------|---------|
| **SMTP Host** | Mail server address | smtp.gmail.com |
| **Port** | Server port | 587 (TLS) or 465 (SSL) |
| **Username** | SMTP authentication user | notifications@yourcompany.com |
| **Password** | App-specific password | •••••••• |
| **Encryption** | TLS or SSL | TLS |
| **Sender Name** | Display name | "ABC Pharmacy" |
| **Sender Email** | From address | noreply@yourcompany.com |

3. Click **Test Email** to verify configuration
4. System sends test email to your admin email
5. If successful, click **Save**

**Recommended Providers:**
- SendGrid (high volume, good deliverability)
- Amazon SES (cost-effective for AWS users)
- Mailgun (reliable transactional email)
- Gmail Workspace (small businesses)

**Email Templates:**
Go to **Settings → Email → Templates** to customize:
- Welcome email
- Password reset
- Invoice notification
- Payment receipt
- Low stock alert
- Shift variance alert

### 9.4 Invoice & Receipt Numbering

1. Go to **Settings → Numbering**
2. Configure auto-numbering for each document type:

| Document | Default Pattern | Example |
|----------|----------------|---------|
| **Sales Invoice** | INV-{YYYY}-{0000} | INV-2026-0042 |
| **Sales Order** | SO-{YYYY}-{0000} | SO-2026-0089 |
| **Quotation** | QT-{YYYY}-{0000} | QT-2026-0015 |
| **Purchase Order** | PO-{YYYY}-{0000} | PO-2026-0033 |
| **GRN** | GRN-{YYYY}-{0000} | GRN-2026-0012 |
| **Purchase Invoice** | PINV-{YYYY}-{0000} | PINV-2026-0007 |
| **Journal Entry** | JE-{YYYY}-{0000} | JE-2026-0105 |
| **Expense** | EXP-{YYYY}-{0000} | EXP-2026-0044 |

3. **Custom Patterns:**
   - `{YYYY}` = 4-digit year
   - `{YY}` = 2-digit year
   - `{MM}` = Month
   - `{DD}` = Day
   - `{0000}` = Sequential number (auto-incrementing)
   - `{BRANCH}` = Branch code

4. **Starting Number:** Set next sequence number (useful for migration from another system)
5. Click **Save**

> **⚠️ Warning:** Changing numbering patterns mid-year can cause sequence gaps. Plan changes at fiscal year start.

### 9.5 Receipt & Invoice Templates

1. Go to **Settings → Templates**
2. Select template type: **Thermal Receipt** or **A4 Invoice**
3. **Customization Options:**

| Element | Customization |
|---------|--------------|
| **Header** | Logo size and position, company name font |
| **Body** | Column visibility, item description length, barcode display |
| **Footer** | Terms & conditions, thank you message, social media links |
| **Colors** | Primary brand color, accent color |
| **Fonts** | Header font, body font (limited to web-safe fonts) |

4. **Preview:** Real-time preview with sample data
5. Click **Save Template**

**Template Variables:**
Use these placeholders in custom templates:
- `{{company_name}}`, `{{company_address}}`, `{{company_phone}}`
- `{{invoice_number}}`, `{{invoice_date}}`, `{{due_date}}`
- `{{customer_name}}`, `{{customer_address}}`
- `{{subtotal}}`, `{{tax_amount}}`, `{{total}}`
- `{{payment_method}}`, `{{cashier_name}}`

---

## 10. Security Administration

### 10.1 Password Policy

1. Go to **Admin → Security → Password Policy**
2. Configure:

| Setting | Recommendation | Description |
|---------|---------------|-------------|
| **Minimum Length** | 8 characters | Shortest allowed password |
| **Complexity** | Enabled | Require uppercase, lowercase, number, symbol |
| **Expiration** | 90 days | Force password change interval (0 = never) |
| **History** | 5 passwords | Prevent reuse of last N passwords |
| **Lockout Threshold** | 5 attempts | Failed logins before temporary lockout |
| **Lockout Duration** | 30 minutes | Time before automatic unlock |
| **Admin Exemption** | No | Admins follow same policy (recommended) |

3. Click **Save Policy**

### 10.2 Two-Factor Authentication (2FA)

**Enforcing 2FA:**
1. Go to **Admin → Security → 2FA Settings**
2. Toggle **Enforce 2FA**
3. Select scope:
   - **All Users:** Everyone must enable 2FA
   - **Admin Roles Only:** Company Admin, Store Manager
   - **Custom:** Select specific roles
4. **Grace Period:** Days allowed before enforcement (e.g., 7 days for users to set up)
5. Click **Save**

**2FA Methods Supported:**
- **TOTP (Time-based One-Time Password):** Google Authenticator, Authy, Microsoft Authenticator
- **SMS OTP:** Backup method (requires SMS gateway configuration)

**Resetting 2FA for Users:**
1. Go to **Admin → Users → [User] → Security**
2. Click **Reset 2FA**
3. User must re-enroll on next login
4. Use only when user loses authenticator device

### 10.3 Session Management

1. Go to **Admin → Security → Active Sessions**
2. View all active user sessions:

| Column | Description |
|--------|-------------|
| **User** | Name and email |
| **IP Address** | Source IP |
| **Location** | Geolocation (if available) |
| **Device/Browser** | User agent summary |
| **Login Time** | Session start |
| **Last Activity** | Most recent action |
| **Session ID** | Unique identifier |

3. **Actions:**
   - **Terminate Session:** Force logout specific user (useful for suspicious activity)
   - **Terminate All Except Mine:** Mass logout for security incidents
   - **View Details:** Full user agent string, full activity log for session

**Session Policies:**
1. Go to **Admin → Security → Session Settings**
2. Configure:
   - **Session Timeout:** Minutes of inactivity before auto-logout (default: 30)
   - **Max Concurrent Sessions:** Per user (default: 3)
   - **IP Binding:** Restrict sessions to originating IP (optional, restrictive)
   - **Device Binding:** Restrict to first device (optional, very restrictive)

### 10.4 Security Monitoring

**AI Security Monitor (if enabled):**
1. Go to **Admin → Security → Security Alerts**
2. View AI-generated alerts:
   - Unusual login times (e.g., 3 AM access)
   - Geographic anomalies (login from new country)
   - Multiple failed attempts
   - Permission escalation events
   - Bulk data export attempts
   - After-hours admin activity

3. **Alert Severity:**
   - **Low:** Informational
   - **Medium:** Requires review
   - **High:** Immediate action recommended
   - **Critical:** Potential breach

4. **Response Actions:**
   - Mark as reviewed
   - Terminate related sessions
   - Reset user password
   - Temporarily disable user account
   - Escalate to RIBDIGI Support

---

## 11. Maintenance & Monitoring

### 11.1 System Health Dashboard

**Super Admin Only:**
1. Go to **Admin → System → Health**
2. Monitor:

| Metric | Healthy Threshold | Action if Exceeded |
|--------|-------------------|-------------------|
| **Database CPU** | < 70% | Scale up or optimize queries |
| **Database Storage** | < 80% | Archive old data or expand storage |
| **API Response Time** | < 200ms | Investigate slow endpoints |
| **Error Rate** | < 1% | Review error logs |
| **Queue Depth** | < 100 jobs | Scale Celery workers |
| **Cache Hit Rate** | > 85% | Review cache strategy |

### 11.2 Scheduled Maintenance

1. Go to **Admin → System → Maintenance Windows**
2. Schedule maintenance:
   - **Date and Time:** Low-activity period
   - **Duration:** Estimated downtime
   - **Scope:** Full system or specific modules
   - **Notification:** Auto-email all users 72 hours, 24 hours, and 1 hour before

3. **Maintenance Mode:**
   - Toggle **Maintenance Mode** to show maintenance page to users
   - Allow admin access during maintenance for testing
   - Auto-disable after scheduled duration

### 11.3 Data Archival

For long-term data management:

1. Go to **Admin → System → Data Archival**
2. Configure archival rules:

| Data Type | Archival Age | Action |
|-----------|-------------|--------|
| **Completed Sales Orders** | 2 years | Move to archive; keep summary |
| **Old Audit Logs** | 2 years | Compress and move to cold storage |
| **Notification History** | 90 days | Delete |
| **Backup Archives** | 30 days per retention policy | Delete per policy |

3. **Archive Storage:** Archived data remains queryable but slower to access
4. **Restore from Archive:** Request restoration (may take 24–48 hours)

---

## 12. Troubleshooting

### 12.1 User Access Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Account is deactivated" | User status = Inactive | Admin: Users → Activate |
| "Invalid credentials" | Wrong password or email | Reset password; verify email spelling |
| "Account locked" | Too many failed attempts | Wait 30 min or admin manually unlocks |
| "2FA code invalid" | Time sync issue or wrong code | User: Sync device time; Admin: Reset 2FA |
| "Insufficient permissions" | Role lacks module access | Admin: Update role permissions |
| "Session expired" | Inactivity timeout | Re-login |

### 12.2 Data Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Product not found in POS" | Inactive or no stock | Check product status and warehouse assignment |
| "Invoice won't post" | Unbalanced journal | Verify debits equal credits |
| "Tax calculation wrong" | Wrong tax rate assigned | Check product category tax mapping |
| "Negative stock" | Setting disabled | Enable in Settings → Inventory or adjust stock |
| "Duplicate invoice number" | Numbering conflict | Check numbering sequence; reset if needed |

### 12.3 System Performance

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow page loads | Large dataset | Apply date filters; use pagination |
| Report generation timeout | Complex date range | Narrow date range; run during off-peak |
| POS lag | Network latency | Check internet; use offline mode if available |
| Backup failure | Storage full | Free space or upgrade plan |
| Email not sending | SMTP misconfiguration | Test SMTP settings; check spam folders |

### 12.4 Emergency Procedures

**Suspected Security Breach:**
1. Go to **Admin → Security → Active Sessions**
2. Terminate all suspicious sessions
3. Reset passwords for affected users
4. Enable maintenance mode if necessary
5. Export audit logs for analysis
6. Contact RIBDIGI Support immediately

**Data Corruption:**
1. Do not attempt manual database edits
2. Note the affected records and symptoms
3. Restore from most recent clean backup
4. Contact RIBDIGI Support for assistance

---

## 13. Appendix

### A. Quick Reference Commands

| Task | Navigation Path |
|------|----------------|
| Create tenant | Tenant Management → Create Tenant |
| Add user | Admin → Users → Create User |
| Edit role permissions | Admin → Roles & Permissions → [Role] → Edit |
| Run manual backup | Admin → Backup & Recovery → Manual Backup |
| Restore database | Admin → Backup & Recovery → Restore |
| View audit logs | Admin → Audit Logs |
| Configure email | Settings → Email |
| Set tax rates | Admin → Company Setup → Tax Configuration |
| Manage stores | Admin → Company Setup → Stores |
| Security settings | Admin → Security |

### B. Contact & Support

| Issue Type | Contact Method |
|------------|---------------|
| **Technical Support** | support@ribdigi.com |
| **Security Incidents** | security@ribdigi.com |
| **Billing Inquiries** | billing@ribdigi.com |
| **Emergency Hotline** | +1-800-RIBDIGI (24/7 for Enterprise) |
| **Documentation** | docs.ribdigi.com |
| **Status Page** | status.ribdigi.com |

### C. Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | August 2026 | RIBDIGI Product Team | Initial MVP release |

---

<p align="center">
  <strong>RIBDIGI BUSINESS ERP — Administrator Manual</strong><br>
  <em>One ERP Platform. Unlimited Business.</em><br><br>
  © 2026 RIBDIGI. All rights reserved.<br>
  <strong>CONFIDENTIAL — Authorized Use Only</strong>
</p>
