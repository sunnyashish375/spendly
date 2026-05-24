# Spec: Backend Routes for Profile Page

## Overview
The profile page (`/profile`) currently performs all expense-statistics computation inline
inside the route function — summing totals, grouping by category, slicing recent entries.
This step moves that logic into dedicated `database/db.py` helpers, adds a fixed `CATEGORIES`
constant, and introduces a `/profile/expenses` route that lists every expense for the logged-in
user (not just the 5 most recent shown on the dashboard). The result is a cleaner, testable
backend layer that all future CRUD steps (7–9) will build on top of.

## Depends on
- Step 01 — Database Setup (`get_db()`, `expenses` table)
- Step 02 — Registration (users in DB, session pattern)
- Step 03 — Login and Logout (`session['user_id']` set on login)
- Step 04 — Profile Page Design (`/profile` route and `profile.html` template exist)

## Routes
- `GET /profile` — already exists; update to call new DB helpers instead of computing inline — logged-in only
- `GET /profile/expenses` — new route; renders a full paginated expense list for the logged-in user — logged-in only

## Database changes
No new tables or columns. Three new helper functions added to `database/db.py`:

- `get_expense_stats(user_id)` — returns a dict with `total_spent` (float), `expense_count` (int), and `category_totals` (list of `(category, amount, pct)` tuples sorted by amount descending)
- `get_recent_expenses(user_id, limit=5)` — returns the N most recent expense rows for the user, ordered by `date DESC`
- `get_all_expenses(user_id)` — returns every expense row for the user, ordered by `date DESC`

Also add a module-level constant to `database/db.py`:
```python
CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
```

## Templates
- **Modify:** `templates/profile.html` — no structural changes; template variables passed from the route remain the same (`total_spent`, `expense_count`, `category_totals`, `recent_expenses`). The route now sources these from helpers instead of inline code.
- **Create:** `templates/expenses.html` — extends `base.html`; renders a full expense table with columns: Date, Category (badge), Description, Amount; shows an empty-state message when no expenses exist; links back to `/profile`

## Files to change
- `database/db.py` — add `CATEGORIES` constant; add `get_expense_stats()`, `get_recent_expenses()`, `get_all_expenses()` helpers
- `app.py` — refactor `profile()` route to use `get_expense_stats()` and `get_recent_expenses()` instead of inline computation; add new `expenses_list()` route for `GET /profile/expenses`; import new helpers

## Files to create
- `templates/expenses.html` — full expense list page

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here; do not expose `password_hash` to any template)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Unauthenticated visitors to `/profile/expenses` must be redirected to `url_for('login', next='/profile/expenses')`
- `get_expense_stats()` must handle the zero-expenses case: `total_spent=0.0`, `expense_count=0`, `category_totals=[]`
- The `pct` in `category_totals` must be an integer (use `round()`); guard against division-by-zero when `total_spent == 0`
- `get_recent_expenses()` and `get_all_expenses()` must close the DB connection before returning
- The `profile()` route must not contain any arithmetic or grouping logic after this step — all computation belongs in `get_expense_stats()`
- `CATEGORIES` must be imported into `app.py` and passed to any template that renders a category selector (not yet needed this step, but the import must exist for step 7)

## Definition of done
- [ ] Visiting `/profile` while logged in still renders correctly with the same data as before (total spent, expense count, category breakdown, 5 most recent expenses)
- [ ] The `profile()` route function contains no `sum()`, no `for` loop over expenses, and no inline arithmetic — all sourced from `get_expense_stats()` and `get_recent_expenses()`
- [ ] Visiting `/profile/expenses` while logged in renders a full table of all expenses for that user
- [ ] Visiting `/profile/expenses` while logged out redirects to `/login?next=%2Fprofile%2Fexpenses`
- [ ] A user with zero expenses sees an empty-state message on `/profile/expenses` (no 500 error)
- [ ] `get_expense_stats()` returns `total_spent=0.0`, `expense_count=0`, `category_totals=[]` for a user with no expenses
- [ ] `CATEGORIES` is defined in `database/db.py` and imported in `app.py`
- [ ] `expenses.html` links back to `/profile` using `url_for('profile')`
- [ ] App starts without errors after all changes
