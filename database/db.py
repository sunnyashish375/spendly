import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'spendly.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def create_user(name, email, password):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_expenses_by_user_id(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_recent_expenses(user_id, limit=5):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_all_expenses(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_expense_stats(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT amount, category FROM expenses WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    conn.close()
    total_spent = sum(r["amount"] for r in rows)
    expense_count = len(rows)
    raw_totals = {}
    for r in rows:
        raw_totals[r["category"]] = raw_totals.get(r["category"], 0) + r["amount"]
    category_totals = [
        (cat, amt, round(amt / total_spent * 100) if total_spent else 0)
        for cat, amt in sorted(raw_totals.items(), key=lambda x: x[1], reverse=True)
    ]
    return {
        "total_spent": total_spent,
        "expense_count": expense_count,
        "category_totals": category_totals,
    }


def get_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM expenses ORDER BY category ASC"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def seed_db():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        conn.close()
        return

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    expenses = [
        (user_id, 12.50,  "Food",          "2026-05-01", "Lunch at cafe"),
        (user_id, 45.00,  "Transport",     "2026-05-03", "Monthly bus pass"),
        (user_id, 120.00, "Bills",         "2026-05-05", "Electricity bill"),
        (user_id, 35.00,  "Health",        "2026-05-08", "Pharmacy"),
        (user_id, 25.00,  "Entertainment", "2026-05-10", "Movie tickets"),
        (user_id, 89.99,  "Shopping",      "2026-05-12", "New shoes"),
        (user_id, 8.75,   "Food",          "2026-05-14", "Coffee and snacks"),
        (user_id, 15.00,  "Other",         "2026-05-16", "Miscellaneous"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
