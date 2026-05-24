import os
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, abort
from markupsafe import Markup
from werkzeug.security import check_password_hash
from database.db import (
    get_db, init_db, seed_db, create_user,
    get_user_by_email, get_user_by_id,
    get_recent_expenses, get_all_expenses,
    get_expense_stats, get_categories,
    get_expense_stats_filtered, get_expenses_filtered,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

with app.app_context():
    init_db()
    seed_db()


def _parse_date_range(args):
    s = args.get("start", "").strip()
    e = args.get("end", "").strip()
    if not s or not e:
        return None, None
    try:
        if date.fromisoformat(s) > date.fromisoformat(e):
            return None, None
    except ValueError:
        return None, None
    return s, e


def _resolve_preset(start_date, end_date):
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last30_start = today - timedelta(days=29)

    if start_date is None:
        return "all_time", "All time"
    if start_date == first_this.isoformat() and end_date == today.isoformat():
        return "this_month", first_this.strftime("%B %Y")
    if start_date == last_month_start.isoformat() and end_date == last_month_end.isoformat():
        return "last_month", last_month_start.strftime("%B %Y")
    if start_date == last30_start.isoformat() and end_date == today.isoformat():
        return "last_30", "Last 30 days"
    return "custom", f"{start_date} – {end_date}"


def _build_presets(endpoint):
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last30_start = today - timedelta(days=29)

    def u(s, e):
        return Markup(url_for(endpoint, start=s.isoformat(), end=e.isoformat()))

    return {
        "this_month": u(first_this, today),
        "last_month": u(last_month_start, last_month_end),
        "last_30":    u(last30_start, today),
        "all_time":   Markup(url_for(endpoint)),
    }


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([name, email, password, confirm_password]):
        return render_template("register.html", error="All fields are required.", name=name, email=email)

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.", name=name, email=email)

    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.", name=name, email=email)

    try:
        user_id = create_user(name, email, password)
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.", name=name, email=email)

    session["user_id"] = user_id
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        next_url = request.args.get("next", "")
        return render_template("login.html", next=next_url)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    next_url = request.form.get("next", "")

    if not email or not password:
        return render_template("login.html", error="Invalid email or password.", email=email, next=next_url)

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email, next=next_url)

    session.clear()
    session["user_id"] = user["id"]

    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        abort(405)
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login", next="/profile"))
    user = get_user_by_id(session["user_id"])
    if user is None:
        abort(404)
    created_raw = user["created_at"]
    member_since = (
        datetime.strptime(created_raw, "%Y-%m-%d %H:%M:%S").strftime("%B %d, %Y")
        if created_raw else "—"
    )
    start_date, end_date = _parse_date_range(request.args)
    stats = get_expense_stats_filtered(session["user_id"], start_date, end_date)
    recent_expenses = get_recent_expenses(session["user_id"], limit=5)
    active_preset, period_label = _resolve_preset(start_date, end_date)
    presets = _build_presets("profile")
    expenses_url = (
        url_for("expenses_list", start=start_date, end=end_date)
        if start_date else url_for("expenses_list")
    )
    return render_template(
        "profile.html",
        name=user["name"],
        email=user["email"],
        member_since=member_since,
        total_spent=stats["total_spent"],
        expense_count=stats["expense_count"],
        category_totals=stats["category_totals"],
        recent_expenses=recent_expenses,
        presets=presets,
        active_preset=active_preset,
        period_label=period_label,
        start_date=start_date or "",
        end_date=end_date or "",
        expenses_url=expenses_url,
    )


@app.route("/profile/expenses")
def expenses_list():
    if not session.get("user_id"):
        return redirect(url_for("login", next="/profile/expenses"))
    start_date, end_date = _parse_date_range(request.args)
    expenses = get_expenses_filtered(session["user_id"], start_date, end_date)
    active_preset, period_label = _resolve_preset(start_date, end_date)
    presets = _build_presets("expenses_list")
    return render_template(
        "expenses.html",
        expenses=expenses,
        presets=presets,
        active_preset=active_preset,
        period_label=period_label,
        start_date=start_date or "",
        end_date=end_date or "",
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
