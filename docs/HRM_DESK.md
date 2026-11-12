# HRM desk

HRM is its own industry on `hrm_*` tables: staff records, leave, attendance and payroll. It has no products, sales or till. Its menu has only HR work and account settings.

## Sidebar

An HRM company gets its own sidebar (`HRM_NAV_GROUPS`): Dashboard; People (Employees, Leave, Attendance); Pay (Payroll, Reports, Pay rates); My pay and leave; Sign-in accounts (`/users`); Notifications; Help; Settings. No retail, expense or accounting menus and no in-page tab strip.

## Screens (`/hrm`)

- **Today:** staff, leave to decide, who is away, the pay bill, what is still to pay.
- **People:** add staff, record someone leaving.
- **Leave:** record, approve or turn down.
- **Attendance:** mark a day.
- **Payroll:** draw up a month, change a bonus or deduction, approve, pay, print payslips.
- **Reports:** payroll by month, staff by department, leave taken.
- **Settings:** leave days, working days, SSNIT rates, PAYE bands.
- **My pay and leave:** a person's own leave balance, leave and payslips.

## Payroll

Rates live in `hrm_settings`. They start at employee SSNIT 5.5%, employer SSNIT 13% and these monthly PAYE bands: 490 at 0%, 110 at 5%, 130 at 10%, 3,166.67 at 17.5%, 16,000 at 25%, 30,520 at 30%, the rest at 35%. **These are starting values. A company must check them against the current GRA and SSNIT tables before paying anyone.**

For each person:

1. Earned basic is basic less unpaid leave days, at basic divided by working days.
2. Gross is earned basic plus allowances and bonus.
3. Staff SSNIT is taken on earned basic.
4. PAYE is taken on gross less staff SSNIT, band by band.
5. Net is gross less SSNIT, PAYE and other deductions. Net below zero is refused.

Approving books the cost: debit 6200 and 6210, credit 2170 (net), 2175 (other deductions held), 2180 (PAYE), 2190 (SSNIT Tier 1, both shares), 2192 (Tier 2) and 2195 (Tier 3). An approved run cannot change. Salaries, PAYE and SSNIT are each paid once and clear their own liability. Other deductions stay in 2175 until the company deals with them by journal.

A month can have only one run. Someone who left is paid for the month they left, and not after.

## Dated rates, Tier 2 and Tier 3

Payroll arithmetic is Decimal throughout (`backend/app/hrm_payroll.py`, no floats). The rates are data, not code:

- **Dated rules** (`hrm_statutory_rates`, Settings → Dated rates, `GET|POST|DELETE /hrm/statutory-rates`): staff and company SSNIT %, Tier 2 % of insurable pay, a monthly SSNIT cap (maximum insurable earnings, blank for none), Tier 3 tax relief %, PAYE bands, rounding (nearest pesewa or down), and a note of where the figures came from. A month uses the newest row starting on or before its first day. With no dated rows, the older Settings rates are used exactly as before.
- A row an approved payroll used is locked: it cannot be removed, and a new row cannot start inside or before an approved month. A change in the law is a new row from its start date.
- **Tier 1 / Tier 2:** staff + company SSNIT together, on earned basic up to the cap. Tier 2 (its % of insurable pay) is booked to 2192 and paid to the trustee with **Pay Tier 2**; the rest is Tier 1 in 2190, paid with **Pay SSNIT**. Tier 2 % of 0 keeps everything in 2190.
- **Tier 3:** voluntary, a % of earned basic set on each person. It comes off net pay, goes to 2195 and is paid with **Pay Tier 3**. It is relieved from PAYE up to the Tier 3 relief %.
- PAYE is taken on gross less staff SSNIT less relieved Tier 3. Each payslip keeps the rates it used (`rates_used`).
- Staff records also hold the Ghana Card (`GHA-123456789-0`) and Mobile Money number.

**The figures are not checked against GRA or SSNIT by the system.** The desk does not file with GRA or SSNIT.

## Salary changes and corrections

- **Change salary** (People, `GET|POST /hrm/employees/{id}/salary`): new basic and allowances from a date, with a reason. Payroll uses the change in force on the month's first day (a mid-month change counts from the next month). The history stays.
- An approved payroll is never edited. A change dated on or before an approved month raises **back pay** for each such month on the next payroll: the basic difference attracts SSNIT and PAYE, an allowance difference PAYE only.
- **Corrections** (Payroll, `GET|POST|DELETE /hrm/adjustments`): any other mistake put right on the next payroll, plus or minus, with a reason. A thrown-away draft hands its corrections back; a correction already on a draft is cancelled by throwing the draft away.

## PAYE and SSNIT schedules, yearly tax statement

Reports → PAYE and SSNIT schedules (`GET /hrm/reports/paye|ssnit?period=`) list each person's figures from approved payslips with CSV downloads, and name anyone missing a TIN/Ghana Card or SSNIT number. **Print statement** (`GET /hrm/reports/tax-statement`) gives one person's year month by month; staff print their own from My pay and leave (`GET /hrm/me/tax-statement`). These are working papers for the company's own returns: nothing is filed with GRA or SSNIT.

## Loans and salary advances

Payroll → Loans and advances (`/hrm?tab=loans`, `GET|POST /hrm/loans`, `POST /hrm/loans/{id}/decide|repay`); staff ask for their own under My pay and leave (`POST /hrm/me/loans`).

- A **loan** is repaid by a fixed monthly amount; a **salary advance** is repaid in full from the next payroll.
- It is decided by a payroll manager who is neither the borrower nor the person who asked. Turning it down needs a reason.
- Approving pays it out once: debit 1150 Staff Loans and Advances, credit cash or bank.
- Each payroll drawn up takes the monthly amount (capped at the balance, and never taking net pay below nil). Approving the payroll credits 1150 and lowers the balance; at nil the loan is settled. A loan can also be paid back in cash.
- No interest is charged: the balance is the amount lent.

## Public holidays

Leave → Public holidays (`GET|POST|DELETE /hrm/holidays`). Leave and unpaid days skip these days. **Show Ghana's usual holidays** offers a starting list (fixed dates, Good Friday, Easter Monday, Farmers' Day) to tick and save. It is not authoritative: check it against the Public Holidays Act and government notices, enter a moved holiday on the day taken off, and add the two Eid holidays each year when announced.

## Two people for payroll

Pay rates → **Someone other than the person who drew up a payroll must approve it** (`two_person_payroll`, off by default for one-person offices). When on, approving your own run is refused (403 `PAYROLL_SECOND_PERSON`).

## People work (`hrm_people.py`, `hrm_people_api.py`, screen `PeopleWork.tsx`)

| Area | What it does | Who |
| --- | --- | --- |
| Hiring | Jobs, candidates moved one stage at a time (applied → screening → interview → offer → hired, or not taken). An offer names the basic; **Hire** makes the staff record and an optional probation contract, and marks the job filled when its openings are taken. | Officers up to interview; offer and hire need an HR manager |
| Reviews | Goals with weights adding to 100; the person scores themselves (My pay and leave), then a reviewer scores 1–5. The overall is the weighted average. Nobody finishes their own review. | HR manager |
| Training | Courses (mandatory or not, valid for N months), who did what, due dates, and mandatory courses each person has not done or has let lapse. | Officers |
| Contracts | Kind, dates, probation; contracts ending and probation due in the next 30 days; **Confirm** probation. Fixed-term needs an end date. | Officers |
| Cases | Disciplinary cases and grievances (staff raise their own). Closed with a recorded outcome and note. Only HR managers see the details; staff see that a case exists and how it ended. | HR manager |
| Staff kit | Items issued to staff and handed back, with condition. | Officers |
| Expense claims | Staff claim money spent; someone other than the claimant approves, which pays it back (debit 6000, credit cash/bank). Not through payroll. | HR manager |
| Notices | Announcements and HR policies staff read under My pay and leave, until taken down. | Officers |

Not built: document uploads (contracts, CVs and receipts are recorded by reference only), e-signatures, interview panels and calendar invites, 360-degree feedback, training budgets.

## Leave

Days are working days, Monday to Friday, less the public holidays entered for the company. Someone with **Reports to** set goes through two steps: their manager agrees or turns it down first (My pay and leave → Leave from my team, `GET /hrm/team/leave`), then HR decides. HR may decide at either step; skipping the manager is recorded in the audit. Nobody with no manager waits for one. Annual leave is earned **all at the start of the year** (less the months before someone started) or **a twelfth each month**; up to the **carry-over days** unused last year roll in (last year's own allowance only, not stacked). Annual leave cannot pass the allowance, counting requests still waiting. Leave cannot overlap. Turning leave down needs a reason. Nobody decides their own leave. Approved unpaid leave comes off that month's pay when the run is drawn up.

## Staff jobs

`hrm.job` limits each role inside `require_permission("hrm", …)`, and `HRM_ROLE_HREFS` in `frontend/lib/tenantNav.ts` mirrors it for menus.

| Role | Can do |
| --- | --- |
| HR Manager, company admin | everything |
| HR Officer | people, leave, attendance; sees no pay |
| Employee | their own leave and payslips, found by the email on their record |

Staff only see a payslip once the run is approved.

## Demo

`PYTHONPATH=. python scripts/seed_hrm_demo.py` creates `demo-hrm-rec` (Bright Path Services; owner, HR officer and employee logins). It refuses to run in production.
