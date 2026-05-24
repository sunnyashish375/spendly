# Spec: Date Filter for Profile Page

## Overview
The profile page currently shows statistics and expenses for all time with no way to narrow
the view. This step adds date-range filtering to both `/profile` and `/profile/expenses` so
users can focus on a specific period. A filter bar with preset buttons ("This Month",
"Last Month", "Last 30 Days", "All Time") plus optional custom `start` / `end` date inputs
passes query parameters back to the same routes. The backend resolves the active range,
passes it to new date-aware DB helpers, and re-renders the page with filtered totals,
category breakdown, and expense rows.

## Depends on
- Step 01 — Database Setup (`expenses` table with `date TEXT` column)
- Step 02 — Registration (session pattern)
- Step 03 — Login and Logout (`session['user_id']` set on login)
- Step 04 — Profile Page Design (`profile.html` template)
- Step 05 — Backend Routes for Profile Page (`get_expense_stats`, `get_all_expenses`,
  `get_recent_expenses` helpers; `/profile/expenses` route)

## Routes
- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — existing route; now reads optional
  `start` / `end` query params, resolves the active date range, and passes filtered data to
  the template — logged-in only
- `GET /profile/expenses?start=YYYY-MM-DD&end=YYYY-MM-DD` — existing route; same filter
  support as `/profile`; renders filtered full expense list — logged-in only

No new routes are introduced.

## Database changes
No new tables or columns. Two new helper functions added to `database/db.py`:

- `get_expense_stats_filtered(user_id, start_date=None, end_date=None)` — same return
  shape as `get_expense_stats` (`total_spent`, `expense_count`, `category_totals`) but
  accepts optional ISO-8601 date strings; when provided, adds `WHERE date BETWEEN ? AND ?`
  to the query using parameterised placeholders
- `get_expenses_filtered(user_id, start_date=None, end_date=None)` — same return shape
  as `get_all_expenses` (rows ordered by `date DESC`) with the same optional date-range
  filtering

The existing `get_expense_stats`, `get_all_expenses`, and `get_recent_expenses` helpers
remain unchanged — they are still used by other callers.

## Templates
- **Modify:** `templates/profile.html` — add a filter bar above the stats cards containing:
  preset period buttons ("This Month", "Last Month", "Last 30 Days", "All Time") that
  navigate to `/profile?start=…&end=…`; a custom date range form (`start` / `end` inputs,
  "Apply" button) that submits GET to `/profile`; display the active period label below the
  filter bar; all links and form action use `url_for('profile')`
- **Modify:** `templates/expenses.html` — add the same filter bar above the expense table;
  preset links target `url_for('expenses_list')`; form action targets `url_for('expenses_list')`

## Files to change
- `database/db.py` — add `get_expense_stats_filtered()` and `get_expenses_filtered()` helpers
- `app.py` — update `profile()` to read `start` / `end` query params, resolve period,
  call `get_expense_stats_filtered()` and `get_recent_expenses()`; update `expenses_list()`
  to read `start` / `end` params and call `get_expenses_filtered()`; import new helpers

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here; never expose `password_hash` to templates)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date range is validated in the route: `start` must be ≤ `end`; if invalid or absent, fall
  back to "All Time" (no date filter applied)
- Date strings are stored and compared as ISO-8601 (`YYYY-MM-DD`); use Python's
  `datetime.date.today()` to compute preset ranges — never hardcode dates
- `get_expense_stats_filtered` and `get_expenses_filtered` must each close the DB
  connection before returning
- `get_expense_stats_filtered` must handle zero-expenses case:
  `total_spent=0.0`, `expense_count=0`, `category_totals=[]`
- The "This Month" preset is the 1st of the current month through today
- The "Last Month" preset is the 1st through the last day of the previous month
- The "Last 30 Days" preset is today minus 29 days through today
- Active filter params must be echoed back into the template so preset buttons and the
  custom form can reflect the current selection (e.g., highlight active preset button)
- `get_recent_expenses` on `/profile` always shows the 5 most recent across all time
  regardless of the active filter — only stats and the "View all expenses" link include
  the active filter

## Definition of done
- [ ] Visiting `/profile` with no query params renders all-time stats (same as before)
- [ ] Visiting `/profile?start=2026-05-01&end=2026-05-31` shows only May 2026 stats and
  category breakdown
- [ ] The filter bar appears on `/profile` with four preset buttons and a custom date form
- [ ] Clicking "This Month" navigates to `/profile?start=…&end=…` with the correct dates
- [ ] Clicking "Last Month" navigates to the first/last day of the previous calendar month
- [ ] Clicking "Last 30 Days" navigates to a 30-day window ending today
- [ ] Clicking "All Time" navigates to `/profile` with no query params
- [ ] The filter bar appears on `/profile/expenses` with the same presets targeting
  `expenses_list`
- [ ] Visiting `/profile/expenses?start=2026-05-01&end=2026-05-31` shows only May expenses
- [ ] A user with no expenses in the selected range sees an empty-state message (no 500 error)
- [ ] Invalid date ranges (start > end, non-ISO strings) fall back gracefully to all-time
- [ ] Active preset button is visually distinguished (e.g., different class) from inactive ones
- [ ] App starts without errors after all changes
