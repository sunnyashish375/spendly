import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id, get_expenses_by_user_id

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

with app.app_context():
    init_db()
    seed_db()


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
    expenses = get_expenses_by_user_id(session["user_id"])
    total_spent = sum(e["amount"] for e in expenses)
    expense_count = len(expenses)
    raw_totals = {}
    for e in expenses:
        raw_totals[e["category"]] = raw_totals.get(e["category"], 0) + e["amount"]
    category_totals = [
        (cat, amt, round(amt / total_spent * 100) if total_spent else 0)
        for cat, amt in sorted(raw_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    recent_expenses = expenses[:5]
    return render_template(
        "profile.html",
        name=user["name"],
        email=user["email"],
        member_since=member_since,
        total_spent=total_spent,
        expense_count=expense_count,
        category_totals=category_totals,
        recent_expenses=recent_expenses,
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
