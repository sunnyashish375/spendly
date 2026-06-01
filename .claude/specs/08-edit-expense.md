# Spec: Edit Expense

## Overview
Users currently have no way to correct a previously entered expense — the
`/expenses/<id>/edit` route is a stub that returns a plain string. This step
replaces that stub with a real GET+POST route: a pre-filled form where a
logged-in user can update the amount, category, date, and description of one
of their own expenses, then save it. Ownership is verified on every request so
users can never edit another user's data. Two new DB helpers support the
feature: one to fetch a single expense with an ownership check, and one to
apply the update.

## Depends on
- Step 01 — Database Setup (`expenses` table schema)
- Step 02 — Registration (session pattern, `users` table)
- Step 03 — Login and Logout (`session['user_id']` set on login)
- Step 05 — Backend Routes for Profile Page (profile route live, `ALLOWED_CATEGORIES` defined)
- Step 07 — Add Expense (`add_expense` route pattern, `expenses` rows exist to edit)

## Routes
- `GET /expenses/<int:id>/edit` — render pre-filled edit form for the given expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate submitted values, update the expense row, redirect to `/profile/expenses` on success — logged-in only

## Database changes
No new tables or columns. The existing `expenses` table already has all required
columns.

Two new helper functions added to `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — fetches a single expense row
  WHERE `id = ?` AND `user_id = ?`; returns `None` if not found (handles both
  "not found" and "not owner" in one query)
- `update_expense(expense_id, user_id, amount, category, date, description)` —
  UPDATEs the matching row using parameterised placeholders; commits and closes
  the connection before returning

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; mirrors
  `add_expense.html` layout but:
  - Heading reads "Edit Expense" (not "Add Expense")
  - All four fields pre-filled with the existing expense values
  - Submit button reads "Save Changes"
  - Cancel link points to `url_for('expenses_list')`
  - Error message area displayed when validation fails
- **Modify:** `templates/expenses.html` — add an "Edit" link/button on each row
  using `url_for('edit_expense', id=expense.id)`

## Files to change
- `app.py` — replace the stub `edit_expense` function with a full GET/POST
  handler: redirect to login if unauthenticated; on GET fetch the expense and
  render the pre-filled form (404 if not found or not owned by user); on POST
  validate all fields, call `update_expense()`, redirect to
  `url_for('expenses_list')`; import `get_expense_by_id` and `update_expense`
  from `database.db`
- `database/db.py` — add `get_expense_by_id(expense_id, user_id)` and
  `update_expense(expense_id, user_id, amount, category, date, description)`

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `get_expense_by_id` MUST include `user_id` in the WHERE clause — never fetch
  by `id` alone; this is the ownership guard
- `amount` must be a positive float; reject zero or negative values with an error
- `category` must be one of `ALLOWED_CATEGORIES`; reject anything else with `abort(400)`
- `date` must be a valid ISO-8601 string; validate with `date.fromisoformat()`
- `description` is optional; store `None` if blank
- On validation failure re-render the form with an error message and the
  submitted (not original) values pre-filled
- Unauthenticated requests to GET or POST must redirect to
  `url_for('login', next=f'/expenses/{id}/edit')`
- If `get_expense_by_id` returns `None` the route must call `abort(404)`
- `update_expense()` must commit and close the DB connection before returning
- The route must be registered with `methods=["GET", "POST"]`

## Definition of done
- [ ] `GET /expenses/<id>/edit` redirects to login for unauthenticated users
- [ ] `GET /expenses/<id>/edit` returns 404 for an expense that does not exist
- [ ] `GET /expenses/<id>/edit` returns 404 when the expense belongs to a different user
- [ ] `GET /expenses/<id>/edit` renders the edit form with all four fields pre-filled for a valid owned expense
- [ ] Submitting the form with valid data updates the row in `expenses` and redirects to `/profile/expenses`
- [ ] The updated values are visible in the expenses list immediately after save
- [ ] Submitting with a blank amount shows a validation error and preserves the other submitted values
- [ ] Submitting with amount = 0 or a negative value shows a validation error
- [ ] Submitting with an invalid date shows a validation error
- [ ] Submitting with an invalid category returns a 400 error
- [ ] Submitting with no description stores `NULL` in the database (no error)
- [ ] Each row in the expenses list (`/profile/expenses`) has a working "Edit" link
- [ ] App starts without errors after all changes
