# Spec: Profile Page Design

## Overview
This step implements the `/profile` route and its template, giving logged-in users a dedicated page that displays their account information. The page shows the user's name, email address, and member-since date pulled from the `users` table. Because all future protected features (expense list, add/edit/delete) will follow this same auth-guard pattern, this step establishes the canonical approach: check `session['user_id']`, look up the user record with a new `get_user_by_id()` helper, and redirect unauthenticated visitors to `/login?next=/profile`. A page-specific stylesheet (`profile.css`) keeps the layout self-contained and consistent with Spendly's CSS-variable design system.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table with `id`, `name`, `email`, `created_at`)
- Step 02 — Registration (users exist in the DB; session usage pattern)
- Step 03 — Login and Logout (`session['user_id']` is set on login; `next` redirect pattern)

## Routes
- `GET /profile` — render profile page for the logged-in user — logged-in only (currently a plain-string stub; replace with real implementation)

## Database changes
No new tables or columns. A new helper `get_user_by_id(user_id)` will be added to `database/db.py`. It queries `SELECT * FROM users WHERE id = ?` and returns the row as a `sqlite3.Row` (or `None` if not found — callers should treat this as a 404).

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; displays user name, email, and member-since date; links back to landing
- **Modify:** none

## Files to change
- `app.py` — replace the stub string return in `profile()` with an auth guard and `render_template("profile.html", user=user)`; import `get_user_by_id` from `database.db`
- `database/db.py` — add `get_user_by_id(user_id)` helper

## Files to create
- `templates/profile.html` — profile page template
- `static/css/profile.css` — page-specific styles (card layout, avatar placeholder, info rows)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here, but do not expose `password_hash` to the template)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Unauthenticated visitors must be redirected to `url_for('login', next='/profile')` — never shown the page
- If `get_user_by_id()` returns `None` (user deleted mid-session), call `abort(404)`
- The `created_at` date from SQLite is an ISO string — format it as `%B %d, %Y` in the route before passing to the template (no formatting logic in the template)
- Do not pass `password_hash` to the template context
- Link the stylesheet with `url_for('static', ...)` — never a hardcoded path

## Definition of done
- [ ] Visiting `/profile` while logged in renders the profile page with the correct name, email, and formatted join date
- [ ] Visiting `/profile` while logged out redirects to `/login?next=%2Fprofile`
- [ ] After logging in via that redirect, the user lands back on `/profile`
- [ ] The page displays the user's name, email, and "Member since <date>" text
- [ ] `password_hash` is never present in the rendered HTML source
- [ ] The profile route uses `get_user_by_id()` from `database/db.py` — no inline SQL in `app.py`
- [ ] `profile.css` is linked in `profile.html` and controls the page layout (no inline styles)
- [ ] App starts without errors after all changes
