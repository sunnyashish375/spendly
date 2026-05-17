---
name: spendly-ui-designer
description: >
  Frontend UI Designer for Spendly — a Flask/Jinja2/Vanilla CSS personal expense tracker
  (github.com/sunnyashish375/spendly). Use this skill whenever the user asks to design,
  build, create, redesign, or improve any page, component, or UI element for the Spendly
  project. Trigger on phrases like: "design the ___ page", "create UI for ___",
  "build component for ___", "redesign / improve ___", "add a ___ section",
  or any request to make Spendly look better. Always use this skill for Spendly-related
  UI work — even if the request seems simple.
---

# Spendly UI Designer

Generates modern, production-ready UI for the **Spendly** expense tracker.
**Stack: Flask + Jinja2 + Vanilla CSS + Lucide Icons. No frameworks. No npm.**

---

## Repo Architecture (from CLAUDE.md)

```
spendly/
├── app.py                    # ALL routes — single file, no blueprints
├── database/
│   └── db.py                 # SQLite helpers: get_db(), init_db(), seed_db(), create_user(), get_user_by_email()
├── templates/
│   ├── base.html             # Shared layout — ALL templates must extend this
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   └── *.html                # one file per page
├── static/
│   ├── css/
│   │   ├── style.css         # Global styles
│   │   └── landing.css       # Landing-page-only styles
│   └── js/
│       └── main.js           # Vanilla JS only
└── requirements.txt
```

**Hard rules from the project:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file (e.g. `static/css/expenses.css`), never inline `<style>` tags
- No React, no jQuery, no npm packages — **Vanilla JS only**
- No new pip packages without flagging it
- Always use `url_for()` for internal links — never hardcode URLs
- App runs on **port 5001**, not 5000

---

## Known Routes (from app.py)

| Route | Status | Template |
|-------|--------|----------|
| `GET /` | Done | `landing.html` |
| `GET /register` | Done | `register.html` |
| `GET /login` | Done | `login.html` |
| `GET /logout` | Stub — Step 3 | — |
| `GET /profile` | Stub — Step 4 | — |
| `GET /expenses/add` | Stub — Step 7 | — |
| `GET/POST /expenses/<id>/edit` | Stub — Step 8 | — |
| `GET /expenses/<id>/delete` | Stub — Step 9 | — |

**Do not implement a stub route's backend unless explicitly asked — only design the template.**

---

## Step 0 — Read the Actual Files First (ALWAYS)

Before writing any code, read the real project files:

```bash
# 1. Check base layout and CSS links already in place
cat templates/base.html

# 2. Read the target template if it already exists (for redesign tasks)
cat templates/<relevant>.html

# 3. Read global CSS to extract the design system
cat static/css/style.css

# 4. Check landing CSS for established patterns
cat static/css/landing.css

# 5. Skim app.py for the route that serves this page and what variables it passes
grep -A 15 "def <route_function>" app.py
```

Extract and note:
- **CSS variables / color palette** (look for `:root { }` block)
- **Existing class names** to reuse
- **Jinja2 block names** in `base.html` (`{% block content %}`, `{% block title %}`, etc.)
- **Data shape** passed from Flask (variable names, dict keys)

If `base.html` doesn't define CSS variables yet, use the fallback palette below.

---

## Step 1 — Clarify (only if genuinely unclear)

Ask only if critical info is missing:
- Which page/component?
- Any specific data to display not obvious from the routes?

If the request is clear — **skip asking and produce code.**

---

## Step 2 — Plan Briefly

Think through layout internally. Tell the user 2–3 lines on what you're building and why, then go straight to code.

---

## Step 3 — Write the Code

### Template structure

```html
{% extends "base.html" %}

{% block title %}Page Title — Spendly{% endblock %}

{% block content %}
  <!-- page HTML here -->
{% endblock %}
```

**Jinja2 rules:**
- `{{ url_for('static', filename='css/expenses.css') }}` for CSS links
- `{{ url_for('route_name') }}` for all hrefs — **never** hardcode `/login` etc.
- `{{ amount | round(2) }}` for money display
- `{% for expense in expenses %}` — match variable names from `app.py`
- `{% if expenses %}...{% else %}<empty state>{% endif %}` — always handle empty lists
- `{{ error }}` for inline form errors (matches existing `register.html`/`login.html` pattern)
- `session` is available in templates via Flask context

**Auth pattern (from app.py):**
- `session.get("user_id")` — check if logged in
- `session["user_id"]` — current user's ID
- Protected routes redirect: `return redirect(url_for("login") + "?next=" + request.path)`

### CSS rules

**File placement:**
- Global/shared component additions → append to `static/css/style.css` with a comment block
- New page → new file `static/css/<page>.css`
- Link in template: `<link rel="stylesheet" href="{{ url_for('static', filename='css/<page>.css') }}">`
- **Never** write inline `<style>` tags — it violates CLAUDE.md conventions

**Design system — use if not already in style.css:**
```css
:root {
  --primary:       #6366f1;    /* indigo — main CTA */
  --primary-light: #eef2ff;    /* indigo tint — hover backgrounds */
  --primary-dark:  #4f46e5;    /* indigo dark — pressed states */
  --success:       #10b981;    /* green — income / positive */
  --danger:        #ef4444;    /* red — expense / delete */
  --warning:       #f59e0b;    /* amber — alerts / over-budget */
  --text:          #1e293b;    /* near-black — body text */
  --text-muted:    #64748b;    /* slate — secondary/labels */
  --bg:            #f8fafc;    /* off-white — page background */
  --surface:       #ffffff;    /* white — cards */
  --border:        #e2e8f0;    /* light grey — dividers */
}
```

**Spacing — strict 8px grid:** 4 / 8 / 16 / 24 / 32 / 48px

**Component rules:**
- Cards: `border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); background: var(--surface); padding: 24px;`
- Buttons: `border-radius: 8px; padding: 10px 20px; font-weight: 500;`
- Inputs: `border-radius: 8px; border: 1.5px solid var(--border); padding: 10px 14px;`
- Input focus: `border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px var(--primary-light);`
- Mobile breakpoint: `@media (max-width: 768px)`

### Vanilla JS rules

- Write in `static/js/main.js` or a new `static/js/<page>.js`
- Link: `<script src="{{ url_for('static', filename='js/main.js') }}" defer></script>`
- No jQuery, no frameworks — pure `document.querySelector`, `addEventListener`, `fetch`

### Icons (Lucide)

Check if `base.html` already includes Lucide. If not, add before `</body>`:
```html
<script src="https://unpkg.com/lucide@latest"></script>
<script>lucide.createIcons();</script>
```

Use: `<i data-lucide="wallet"></i>`

**Icon map:**
| Purpose | Icon name |
|---------|-----------|
| Add expense | `plus-circle` |
| Delete | `trash-2` |
| Edit | `pencil` |
| Category | `tag` |
| Wallet / total | `wallet` |
| Income | `trending-up` |
| Expense | `trending-down` |
| Date | `calendar` |
| Filter | `sliders-horizontal` |
| Dashboard | `layout-dashboard` |
| Profile | `user-circle` |
| Settings | `settings` |
| Search | `search` |
| Chart | `bar-chart-2` |
| Logout | `log-out` |
| Empty | `inbox` |
| Alert | `alert-circle` |
| Success | `check-circle` |

---

## Step 4 — Quality Checklist

- [ ] Extends `base.html` with correct block names
- [ ] All links use `url_for()` — no hardcoded paths
- [ ] CSS in separate file, linked in template — no inline `<style>`
- [ ] Colors use CSS variables
- [ ] 8px grid spacing
- [ ] Cards: `border-radius: 12px` + soft shadow
- [ ] Empty states handled
- [ ] Mobile layout: `@media (max-width: 768px)`
- [ ] Lucide icons for all interactive elements
- [ ] Template variables match what `app.py` actually passes

---

## Step 5 — Output Format

1. **Summary** — 2–3 lines: what you built, key design decisions
2. **`templates/<page>.html`** — complete Jinja2 file
3. **`static/css/<page>.css`** — complete CSS file (or labelled block to append to `style.css`)
4. **Flask route snippet** — only if new data context needed
5. **JS file** — only if interactive behaviour needed

No tests. No lorem ipsum — use realistic expense data (₹ amounts, real categories).

---

## Common Component Snippets

### Stat Card
```html
<div class="stat-card">
  <div class="stat-icon"><i data-lucide="wallet"></i></div>
  <div class="stat-body">
    <span class="stat-label">Total Spent</span>
    <span class="stat-value">₹{{ total | round(2) }}</span>
  </div>
</div>
```

### Expense Row
```html
<div class="expense-item">
  <div class="expense-left">
    <span class="category-badge"><i data-lucide="tag"></i> {{ expense.category }}</span>
    <span class="expense-note">{{ expense.note }}</span>
  </div>
  <div class="expense-right">
    <span class="expense-date">{{ expense.date }}</span>
    <span class="expense-amount">₹{{ expense.amount | round(2) }}</span>
    <div class="expense-actions">
      <a href="{{ url_for('edit_expense', id=expense.id) }}" class="btn-icon" title="Edit">
        <i data-lucide="pencil"></i>
      </a>
      <a href="{{ url_for('delete_expense', id=expense.id) }}" class="btn-icon danger" title="Delete">
        <i data-lucide="trash-2"></i>
      </a>
    </div>
  </div>
</div>
```

### Empty State
```html
<div class="empty-state">
  <i data-lucide="inbox"></i>
  <p>No expenses yet.</p>
  <a href="{{ url_for('add_expense') }}" class="btn btn-primary">
    <i data-lucide="plus-circle"></i> Add your first expense
  </a>
</div>
```

### Form Error (matches login.html / register.html pattern)
```html
{% if error %}
  <div class="alert alert-error">
    <i data-lucide="alert-circle"></i> {{ error }}
  </div>
{% endif %}
```

---

## Project-Specific Notes

- **Currency:** Always ₹ (Indian Rupee)
- **Date format:** Check `app.py` for `strftime`; default to `DD Mon YYYY` (e.g. `12 May 2026`)
- **Step stubs:** Routes `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` are stubs — design template only unless backend is explicitly requested
- **Redesigns:** Read current template fully → produce complete replacement, not a diff
- **SQLite FK:** `get_db()` must run `PRAGMA foreign_keys = ON` on every connection — don't assume it's set
- **DB helpers:** `get_db()`, `init_db()`, `seed_db()`, `create_user(name, email, password)`, `get_user_by_email(email)` exist in `database/db.py`