# Spec: Delete Expense

## Overview
Users currently have no way to remove a previously entered expense — the
`/expenses/<id>/delete` route is a stub returning a plain string. This step
replaces that stub with a real GET+POST route: a confirmation page where a
logged-in user can review the expense details before permanently deleting it.
Ownership is verified on every request so users can never delete another
user's data. One new DB helper supports the feature. After deletion the user
is redirected back to the expenses list.

## Depends on
- Step 01 — Database Setup (`expenses` table schema)
- Step 02 — Registration (session pattern, `users` table)
- Step 03 — Login and Logout (`session['user_id']` set on login)
- Step 05 — Backend Routes for Profile Page (profile route live)
- Step 07 — Add Expense (`expenses` rows exist to delete)
- Step 08 — Edit Expense (`get_expense_by_id` helper available, expenses list with action links)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the expense details — logged-in only
- `POST /expenses/<int:id>/delete` — permanently delete the expense row, redirect to `/profile/expenses` on success — logged-in only

## Database changes
No new tables or columns. The existing `expenses` table already has all required
columns.

One new helper function added to `database/db.py`:
- `delete_expense(expense_id, user_id)` — executes `DELETE FROM expenses WHERE id = ? AND user_id = ?`
  using parameterised placeholders; commits and closes the connection before returning

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; shows the
  expense details (amount, category, date, description) and asks "Are you sure
  you want to delete this expense?"; contains a `<form method="POST">` with a
  "Delete" submit button and a Cancel link pointing to `url_for('expenses_list')`
- **Modify:** `templates/expenses.html` — add a "Delete" link/button on each row
  using `url_for('delete_expense', id=expense.id)`

## Files to change
- `app.py` — replace the stub `delete_expense` function with a full GET/POST
  handler: redirect to login if unauthenticated; on GET fetch the expense via
  `get_expense_by_id()` and render the confirmation page (404 if not found or
  not owned); on POST call `delete_expense()` and redirect to
  `url_for('expenses_list')`; import `delete_expense` from `database.db`
- `database/db.py` — add `delete_expense(expense_id, user_id)`

## Files to create
- `templates/delete_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `get_expense_by_id` MUST include `user_id` in the WHERE clause — ownership guard
- `delete_expense` MUST include `user_id` in the WHERE clause — never delete by `id` alone
- The actual deletion must happen only on POST — GET must only render the confirmation page
- The route must be registered with `methods=["GET", "POST"]`
- Unauthenticated requests to GET or POST must redirect to
  `url_for('login', next=f'/expenses/{id}/delete')`
- If `get_expense_by_id` returns `None` on GET, the route must call `abort(404)`
- `delete_expense()` must commit and close the DB connection before returning

## Definition of done
- [ ] `GET /expenses/<id>/delete` redirects to login for unauthenticated users
- [ ] `GET /expenses/<id>/delete` returns 404 for an expense that does not exist
- [ ] `GET /expenses/<id>/delete` returns 404 when the expense belongs to a different user
- [ ] `GET /expenses/<id>/delete` renders the confirmation page with the expense's amount, category, date, and description visible
- [ ] The confirmation page has a "Delete" button (POST form) and a "Cancel" link to `/profile/expenses`
- [ ] Submitting the confirmation form deletes the row from `expenses` and redirects to `/profile/expenses`
- [ ] The deleted expense no longer appears in the expenses list after deletion
- [ ] `POST /expenses/<id>/delete` for an expense owned by a different user returns 404 (ownership re-checked)
- [ ] Each row in the expenses list (`/profile/expenses`) has a working "Delete" link
- [ ] App starts without errors after all changes
