# Spec: Add Expense

## Overview
Users currently have no way to record a new expense from within the app — the
`/expenses/add` route is a stub that returns a plain string. This step replaces
that stub with a real GET+POST route: a form where a logged-in user enters an
amount, category, date, and optional description, submits it, and is redirected
to `/profile` on success. A new DB helper `add_expense()` writes the row into
the existing `expenses` table. This is the first write path in Spendly and
unlocks meaningful data for the profile stats and expense list.

## Depends on
- Step 01 — Database Setup (`expenses` table schema)
- Step 02 — Registration (session pattern, `users` table)
- Step 03 — Login and Logout (`session['user_id']` set on login)
- Step 04 — Profile Page Design (`profile.html` so the success redirect lands somewhere)
- Step 05 — Backend Routes for Profile Page (profile route live)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the expense, redirect to `/profile` on success — logged-in only

## Database changes
No new tables or columns. The existing `expenses` table already has all required
columns (`user_id`, `amount`, `category`, `date`, `description`).

One new helper function added to `database/db.py`:
- `add_expense(user_id, amount, category, date, description)` — inserts one row
  into `expenses` using parameterised placeholders; returns the new row's `id`.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; contains:
  - A numeric `amount` input (required, step="0.01", min="0.01")
  - A `category` `<select>` with a fixed list of options: Food, Transport, Bills,
    Health, Entertainment, Shopping, Other
  - A `date` input (required, type="date", defaults to today's date)
  - A `description` `<textarea>` (optional)
  - A submit button ("Add Expense")
  - An error message area displayed when validation fails
  - A cancel link back to `/profile` using `url_for('profile')`

## Files to change
- `app.py` — replace the stub `add_expense` function with a full GET/POST handler:
  redirect to login if not authenticated; on GET render the form with today's date
  pre-filled; on POST validate inputs, call `add_expense()`, redirect to `/profile`
- `database/db.py` — add `add_expense(user_id, amount, category, date, description)`
  helper

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `amount` must be a positive float; reject zero or negative values with an error
- `category` must be one of the fixed allowed values; reject anything else with a 400
- `date` must be a valid ISO-8601 string (`YYYY-MM-DD`); use `date.fromisoformat()`
  to validate — reject invalid dates with an error message
- `description` is optional; store `None` if blank
- On validation failure, re-render the form with an error message and the previously
  entered values pre-filled (amount, category, date, description)
- Unauthenticated requests to either GET or POST must redirect to
  `url_for('login', next='/expenses/add')`
- `add_expense()` must commit and close the DB connection before returning
- The route function must call `abort(405)` if a method other than GET or POST is used
  (Flask handles this automatically with `methods=["GET", "POST"]`)

## Definition of done
- [ ] `GET /expenses/add` redirects to login for unauthenticated users
- [ ] `GET /expenses/add` renders the add-expense form for logged-in users with today's
  date pre-filled in the date field
- [ ] Submitting the form with valid data inserts a row in `expenses` and redirects
  to `/profile`
- [ ] The new expense appears in the profile's recent expenses and stats after submission
- [ ] Submitting with a blank amount shows a validation error and preserves other field values
- [ ] Submitting with amount = 0 or a negative value shows a validation error
- [ ] Submitting with an invalid date shows a validation error
- [ ] Submitting with an invalid category returns a 400 error
- [ ] Submitting with no description stores `NULL` in the database (no error)
- [ ] The cancel link on the form navigates back to `/profile`
- [ ] App starts without errors after all changes
