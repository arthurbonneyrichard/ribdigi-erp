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

Approving books the cost: debit 6200 and 6210, credit 2170 (net), 2175 (other deductions held), 2180 (PAYE) and 2190 (SSNIT, both shares). An approved run cannot change. Salaries, PAYE and SSNIT are each paid once and clear their own liability. Other deductions stay in 2175 until the company deals with them by journal.

A month can have only one run. Someone who left is paid for the month they left, and not after.

## Leave

Days are working days, Monday to Friday. Public holidays are not known to the system. Annual leave cannot pass the allowance, counting requests still waiting. Leave cannot overlap. Turning leave down needs a reason. Nobody decides their own leave. Approved unpaid leave comes off that month's pay when the run is drawn up.

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
