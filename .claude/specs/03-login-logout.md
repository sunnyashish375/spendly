# Spec: Login and Logout

## Overview
This step implements the login and logout flows for Spendly. The `GET /login` route already renders a form stub; this step adds the `POST /login` handler that validates credentials against the database, starts a Flask session on success, and re-renders the form with an error on failure. It also implements `GET /logout`, which clears the session and redirects to the landing page. Together these two routes complete the authentication loop that all future protected features depend on.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table with `password_hash`)
- Step 02 — Registration (`create_user()`, session usage pattern)

## Routes
- `GET /login` — render login form — public (already exists; upgrade to accept an optional `next` query param and re-populate the email field on validation failure)
- `POST /login` — validate credentials, start session, redirect — public
- `GET /logout` — clear session, redirect to `/` — logged-in (currently a plain-string stub; replace with real implementation)

## Database changes
No new tables or columns. A new helper function `get_user_by_email(email)` will be added to `database/db.py` to look up a user row by email. Returns the row as a `sqlite3.Row` (or `None` if not found).

## Templates
- **Modify:** `templates/login.html` — add `<form method="POST" action="{{ url_for('login') }}">` with fields: `email`, `password`; display an inline error message when passed; re-populate the email field on failure

## Files to change
- `app.py` — convert `/login` to accept GET and POST; implement POST handler; implement `/logout`; import `check_password_hash` from `werkzeug.security`; import `get_user_by_email` from `database.db`
- `database/db.py` — add `get_user_by_email(email)` helper
- `templates/login.html` — add form markup and error display

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed) and `flask.session` (already imported).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compared in plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Invalid credentials must re-render the login form with a generic error ("Invalid email or password") — do not reveal whether the email exists
- Empty email or password must be caught before hitting the DB and re-render the form with an error
- After successful login, set `session['user_id']` and redirect to `/` (or the `next` param if present and safe)
- `GET /logout` must call `session.clear()` and redirect to `url_for('landing')` — never render a template
- Use `abort(405)` if the logout route is hit with POST

## Definition of done
- [ ] Submitting the login form with correct credentials sets `session['user_id']` and redirects to `/`
- [ ] Submitting with an incorrect password re-renders the login form with a generic error — session is not set
- [ ] Submitting with an email that does not exist re-renders the login form with the same generic error
- [ ] Submitting with an empty email or password re-renders the form with an error — no DB query made
- [ ] Visiting `/logout` clears the session and redirects to the landing page
- [ ] After logout, visiting `/logout` again works cleanly (idempotent — no error if already logged out)
- [ ] The login form action points to `/login` via `url_for('login')`
- [ ] The email field is re-populated with the submitted value when the form fails validation
- [ ] App starts without errors after all changes
