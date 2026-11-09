# Gym desk

A gym is its own industry on `gym_*` tables, with its own member list and till. It never writes to retail sales, customers or `pos_sessions`.

## Sidebar

A gym gets its own sidebar (`GYM_NAV_GROUPS`): Dashboard; Front desk (Door, Members, Classes); Plans and money (Plans, Reports); Staff; Notifications; Help; Settings. No retail menus and no in-page tab strip.

## Screens (`/gym`)

- **Today:** active members, visits, classes, money taken, who ends this week.
- **Door:** find a member, let them in or see plainly why not. Refusals are recorded.
- **Members:** the till, add members, sell, renew, freeze, cancel.
- **Classes:** times, trainers, places, bookings, who came.
- **Plans:** price, days, visit limit. A day pass is a one-day plan.
- **Reports:** money taken, plans sold, renewals, new members, visits, who ends soon.

## Rules

- Selling needs an open till. Every movement of money is a row in `gym_payments`.
- A plan is booked as revenue on the day it is sold. It is not spread over the months it covers.
- A renewal starts the day after the current plan ends, so no days are lost.
- A member counts one visit a day. A visit-limited plan stops at its limit.
- Freezing blocks the door. Unfreezing adds the frozen days back, up to 180.
- A new plan price applies to the next sale. Members keep what they paid.
- Cancelling can refund up to what was paid, and reverses the sale and tax in proportion.
- Class booking needs an active membership and a free place.

## Staff jobs

`gym.job` limits each role inside `require_permission("gym", …)`, and `GYM_ROLE_HREFS` in `frontend/lib/tenantNav.ts` mirrors it for menus.

| Role | Can do |
| --- | --- |
| Gym Manager, company admin | everything, including plans, refunds and reports |
| Front Desk | members, selling, the till, the door, classes |
| Trainer | the door and classes; sees no money |

## Demo

`PYTHONPATH=. python scripts/seed_gym_demo.py` creates `demo-gym-rec` (Iron Peak Fitness; owner, front desk and trainer logins). It refuses to run in production.
