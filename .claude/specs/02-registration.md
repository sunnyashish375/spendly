# Spec: Registration

## Overview
This step implements the user registration flow for Spendly. The `GET /register` route already renders the form; this step adds the `POST /register` handler that validates input, checks for duplicate emails, hashes the password, inserts the new user into the database, sets a Flask session, and redirects the user on success. It also wires up Flask's session and flash messaging, which all future authenticated features depend on.

## Depends on
- Step 01 — Database Setup (`get_db()`, `init_db()`, `users` table)

## Routes
- `GET /register` — render registration form — public (already exists as stub; upgrade to pass flashed messages and re-populate field values on validation failure)
- `POST /register` — process registration form, create user, start session — public

## Database changes
No new tables or columns. A new helper function `create_user(name, email, password)` will be added to `database/db.py` to encapsulate the INSERT and return the new user's `id`. The `users` table schema is unchanged.

## Templates
- **Modify:** `templates/register.html` — add `<form method="POST" action="{{ url_for('register') }}">` with fields: `name`, `email`, `password`, `confirm_password`; display flashed error/success messages

## Files to change
- `app.py` — add `app.secret_key`, import `session`, `flash`, `redirect`, `url_for`, `request`; add `POST` to the `/register` route decorator; implement POST handler logic
- `database/db.py` — add `create_user(name, email, password)` helper
- `templates/register.html` — add form markup and flash message display

## Files to create
None.

## New dependencies
No new dependencies. Uses `flask.session`, `flask.flash`, `flask.redirect`, `flask.request`, and `werkzeug.security.generate_password_hash` — all already available.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` inside `create_user()`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session or flash usage; use `os.environ.get('SECRET_KEY', 'dev-secret-change-me')`
- Duplicate email must return the form again with a flashed error — do not raise a 500
- Empty name, email, or password must be caught before hitting the DB
- Password and confirm_password mismatch must be caught in the route and re-render the form
- After successful registration, log the user in immediately (set `session['user_id']`) and redirect to `/login`
- Use `abort(400)` only for truly malformed requests — validation failures re-render the form

## Definition of done
- [ ] Submitting the form with valid data creates a new row in the `users` table with a hashed password
- [ ] The new user is immediately logged in (`session['user_id']` is set) and redirected to `/login` after registration
- [ ] Submitting with an email that already exists re-renders the form with an error message — no duplicate row inserted
- [ ] Submitting with mismatched passwords re-renders the form with an error — no row inserted
- [ ] Submitting with any empty field re-renders the form with an error — no row inserted
- [ ] Passwords are never stored in plain text — `password_hash` column contains a werkzeug hash
- [ ] The registration form action points to `/register` via `url_for('register')`
- [ ] App starts without errors after changes to `app.py`
