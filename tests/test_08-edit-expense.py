"""
tests/test_08-edit-expense.py

Tests for the Edit Expense feature (Step 08).

Spec: .claude/specs/08-edit-expense.md
Routes:
  GET  /expenses/<int:id>/edit  — render pre-filled edit form (auth required, ownership enforced)
  POST /expenses/<int:id>/edit  — validate, update DB, redirect to /profile/expenses

Coverage:
  1.  Auth guard — unauthenticated GET redirects to /login with next param
  2.  Auth guard — unauthenticated POST redirects to /login with next param
  3.  GET 404 — expense does not exist
  4.  GET 404 — expense belongs to a different user
  5.  GET happy path — 200, extends base.html, "Edit Expense" heading, "Save Changes" button
  6.  GET — all four fields pre-filled with stored values
  7.  GET — all 7 allowed categories present in the form
  8.  GET — cancel link points to /profile/expenses
  9.  POST valid data — redirects (302) to /profile/expenses
  10. POST valid data — DB row updated with new values
  11. Updated values visible in expenses list after save
  12. POST blank amount — 200 with error, DB row unchanged
  13. POST amount = 0 — 200 with error, DB row unchanged
  14. POST negative amount — 200 with error, DB row unchanged
  15. POST amount field preservation on validation failure
  16. POST other fields preserved on amount validation failure
  17. POST invalid date — 200 with error, DB row unchanged
  18. POST other fields preserved on date validation failure
  19. POST invalid category — 400, DB row unchanged
  20. POST no description — redirects (302), NULL stored in DB
  21. Edit link on expenses list points to correct URL
  22. User isolation — POST to another user's expense returns 404
"""

import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app wired to an isolated, file-backed SQLite DB per test.

    DB_PATH is monkey-patched so every db helper uses the per-test temp file.
    """
    db_file = str(tmp_path / "test_spendly.db")
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()
        yield flask_app

    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Test client that has registered and is already logged in."""
    client.post(
        "/register",
        data={
            "name": "Test User",
            "email": "testuser@test.com",
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(app, email):
    """Return the DB id for the user with the given email."""
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        return row["id"]


def _insert_expense(app, user_id, amount=50.00, category="Food",
                    date_str="2026-05-10", description="Test lunch"):
    """Insert a single expense row directly and return its id."""
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date_str, description),
        )
        expense_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        return expense_id


def _get_expense(app, expense_id):
    """Return a single expense row as a dict (or None)."""
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


# A convenience payload that is always valid for editing.
VALID_EDIT_FORM = {
    "amount": "75.00",
    "category": "Transport",
    "date": "2026-06-01",
    "description": "Monthly bus pass updated",
}


# ---------------------------------------------------------------------------
# 1 & 2. Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_get_unauthenticated_redirects(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/1/edit must redirect (302)"
        )

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/1/edit")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET must redirect to /login"
        )

    def test_get_unauthenticated_carries_next_param(self, client):
        response = client.get("/expenses/42/edit")
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2F42%2Fedit" in location
            or "next=/expenses/42/edit" in location
        ), "Redirect to /login must carry next=/expenses/42/edit"

    def test_post_unauthenticated_redirects(self, client):
        response = client.post("/expenses/1/edit", data=VALID_EDIT_FORM)
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/1/edit must redirect (302)"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/1/edit", data=VALID_EDIT_FORM)
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_post_unauthenticated_carries_next_param(self, client):
        response = client.post("/expenses/7/edit", data=VALID_EDIT_FORM)
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2F7%2Fedit" in location
            or "next=/expenses/7/edit" in location
        ), "POST redirect to /login must carry next=/expenses/7/edit"


# ---------------------------------------------------------------------------
# 3 & 4. 404 cases
# ---------------------------------------------------------------------------

class Test404Cases:
    def test_get_nonexistent_expense_returns_404(self, auth_client):
        """An expense ID that does not exist at all must return 404."""
        response = auth_client.get("/expenses/99999/edit")
        assert response.status_code == 404, (
            "GET /expenses/99999/edit must return 404 for a non-existent expense"
        )

    def test_get_other_users_expense_returns_404(self, client, app):
        """
        An expense that exists but belongs to a different user must return 404,
        not 200 or 403 — ownership is enforced via the WHERE user_id = ? guard.
        """
        # Register owner (User A) and create an expense
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "usera@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_a = _get_user_id(app, "usera@test.com")
        expense_id = _insert_expense(app, uid_a)

        # Log out User A, register and log in as User B
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "userb@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        # User B tries to access User A's expense
        response = client.get(f"/expenses/{expense_id}/edit")
        assert response.status_code == 404, (
            "GET for another user's expense must return 404 (ownership guard)"
        )

    def test_post_other_users_expense_returns_404(self, client, app):
        """POST to another user's expense must also return 404."""
        client.post(
            "/register",
            data={
                "name": "Owner",
                "email": "owner@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_owner = _get_user_id(app, "owner@test.com")
        expense_id = _insert_expense(app, uid_owner)

        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "Attacker",
                "email": "attacker@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        response = client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        assert response.status_code == 404, (
            "POST to another user's expense must return 404"
        )


# ---------------------------------------------------------------------------
# 5. GET happy path — form rendering
# ---------------------------------------------------------------------------

class TestGetEditExpenseForm:
    def test_get_returns_200_for_owned_expense(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200, (
            "Authenticated GET for an owned expense must return 200"
        )

    def test_get_renders_edit_expense_heading(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Edit Expense" in response.data, (
            "Page must contain the heading 'Edit Expense'"
        )

    def test_get_renders_save_changes_button(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Save Changes" in response.data, (
            "Submit button must be labelled 'Save Changes'"
        )

    def test_get_extends_base_template(self, auth_client, app):
        """All pages extending base.html include the brand name 'Spendly'."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Spendly" in response.data, (
            "Page must extend base.html (brand name 'Spendly' expected)"
        )

    def test_get_renders_amount_input(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b'name="amount"' in response.data, (
            "Form must contain an input named 'amount'"
        )

    def test_get_renders_category_select(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b'name="category"' in response.data, (
            "Form must contain a select named 'category'"
        )

    def test_get_renders_date_input(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b'name="date"' in response.data, (
            "Form must contain an input named 'date'"
        )

    def test_get_renders_description_input(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b'name="description"' in response.data, (
            "Form must contain an input/textarea named 'description'"
        )


# ---------------------------------------------------------------------------
# 6. GET — pre-filled field values
# ---------------------------------------------------------------------------

class TestGetPrefilledFields:
    def test_amount_prefilled(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, amount=123.45)
        response = auth_client.get(f"/expenses/{eid}/edit")
        # The amount may be rendered as "123.45" or "123.4500..." — check the prefix
        assert b"123.45" in response.data or b"123.4" in response.data, (
            "Stored amount (123.45) must be pre-filled in the edit form"
        )

    def test_category_prefilled(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, category="Health")
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Health" in response.data, (
            "Stored category ('Health') must be pre-filled in the edit form"
        )

    def test_date_prefilled(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, date_str="2026-04-15")
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"2026-04-15" in response.data, (
            "Stored date ('2026-04-15') must be pre-filled in the edit form"
        )

    def test_description_prefilled(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Unique prefill description xyz")
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Unique prefill description xyz" in response.data, (
            "Stored description must be pre-filled in the edit form"
        )

    def test_null_description_does_not_break_form(self, auth_client, app):
        """An expense with NULL description must still render the form (no crash)."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description=None)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200, (
            "GET edit form must render 200 even when description is NULL"
        )


# ---------------------------------------------------------------------------
# 7. GET — all allowed categories in the form
# ---------------------------------------------------------------------------

class TestGetAllCategories:
    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
    ])
    def test_all_allowed_categories_present(self, auth_client, app, category):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert category.encode() in response.data, (
            f"Category option '{category}' must appear in the edit form"
        )


# ---------------------------------------------------------------------------
# 8. GET — cancel link points to /profile/expenses
# ---------------------------------------------------------------------------

class TestCancelLink:
    def test_form_has_cancel_link(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"Cancel" in response.data, (
            "Edit form must contain a 'Cancel' link"
        )

    def test_cancel_link_points_to_expenses_list(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/edit")
        assert b"/profile/expenses" in response.data, (
            "Cancel link must point to /profile/expenses"
        )


# ---------------------------------------------------------------------------
# 9 & 10. POST valid data — redirect and DB side effects
# ---------------------------------------------------------------------------

class TestPostHappyPath:
    def test_post_valid_data_redirects(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        assert response.status_code == 302, (
            "Valid POST must redirect (302)"
        )

    def test_post_valid_data_redirects_to_expenses_list(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        assert "/profile/expenses" in response.headers["Location"], (
            "Successful POST must redirect to /profile/expenses"
        )

    def test_post_valid_data_updates_amount(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, amount=10.00)
        auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(app, eid)
        assert row["amount"] == pytest.approx(75.00), (
            "DB amount must be updated to the submitted value (75.00)"
        )

    def test_post_valid_data_updates_category(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, category="Food")
        auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(app, eid)
        assert row["category"] == "Transport", (
            "DB category must be updated to the submitted value ('Transport')"
        )

    def test_post_valid_data_updates_date(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, date_str="2026-01-01")
        auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(app, eid)
        assert row["date"] == "2026-06-01", (
            "DB date must be updated to the submitted value ('2026-06-01')"
        )

    def test_post_valid_data_updates_description(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Old description")
        auth_client.post(f"/expenses/{eid}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(app, eid)
        assert row["description"] == "Monthly bus pass updated", (
            "DB description must be updated to the submitted value"
        )

    def test_post_does_not_alter_other_expenses(self, auth_client, app):
        """Editing one expense must not touch any other expense row."""
        uid = _get_user_id(app, "testuser@test.com")
        eid1 = _insert_expense(app, uid, amount=11.11, description="keep me")
        eid2 = _insert_expense(app, uid, amount=22.22, description="edit me")
        auth_client.post(f"/expenses/{eid2}/edit", data={**VALID_EDIT_FORM, "amount": "99.99"})
        unchanged = _get_expense(app, eid1)
        assert unchanged["amount"] == pytest.approx(11.11), (
            "Editing expense 2 must not change expense 1's amount"
        )
        assert unchanged["description"] == "keep me", (
            "Editing expense 2 must not change expense 1's description"
        )


# ---------------------------------------------------------------------------
# 11. Updated values visible in expenses list
# ---------------------------------------------------------------------------

class TestUpdatedValuesVisibleInList:
    def test_updated_description_visible_in_expenses_list(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Original desc before edit")
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "description": "Updated unique desc after edit xyz"},
        )
        list_response = auth_client.get("/profile/expenses")
        assert b"Updated unique desc after edit xyz" in list_response.data, (
            "Updated description must appear in the expenses list after save"
        )

    def test_updated_amount_visible_in_expenses_list(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, amount=5.00)
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "333.33"},
        )
        list_response = auth_client.get("/profile/expenses")
        assert b"333" in list_response.data, (
            "Updated amount must be visible in the expenses list after save"
        )


# ---------------------------------------------------------------------------
# 12–15. Validation — amount
# ---------------------------------------------------------------------------

class TestValidationAmount:
    @pytest.mark.parametrize("bad_amount", [
        "",       # blank
        "0",      # zero integer
        "0.00",   # zero float
        "-1",     # negative
        "-0.01",  # small negative
        "abc",    # non-numeric
    ])
    def test_invalid_amount_returns_200(self, auth_client, app, bad_amount):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": bad_amount},
        )
        assert response.status_code == 200, (
            f"Amount '{bad_amount}' must fail validation and re-render form (200)"
        )

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "0.00",
        "-1",
        "-0.01",
        "abc",
    ])
    def test_invalid_amount_shows_error_message(self, auth_client, app, bad_amount):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": bad_amount},
        )
        decoded = response.data.decode().lower()
        assert (
            "error" in decoded
            or "positive" in decoded
            or "valid" in decoded
            or "amount" in decoded
        ), f"A visible error message must appear for amount='{bad_amount}'"

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "0.00",
        "-1",
        "abc",
    ])
    def test_invalid_amount_does_not_update_db(self, auth_client, app, bad_amount):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, amount=50.00)
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": bad_amount},
        )
        row = _get_expense(app, eid)
        assert row["amount"] == pytest.approx(50.00), (
            f"DB amount must remain unchanged when submitted amount='{bad_amount}'"
        )

    def test_blank_amount_preserves_category_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "", "category": "Bills"},
        )
        assert b"Bills" in response.data, (
            "Category must be echoed back after blank amount validation error"
        )

    def test_blank_amount_preserves_date_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "", "date": "2026-07-04"},
        )
        assert b"2026-07-04" in response.data, (
            "Date must be echoed back after blank amount validation error"
        )

    def test_blank_amount_preserves_description_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        unique = "preserved desc on blank amount error abc"
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "", "description": unique},
        )
        assert unique.encode() in response.data, (
            "Description must be echoed back after blank amount validation error"
        )

    def test_invalid_amount_text_echoed_in_form(self, auth_client, app):
        """Even a non-numeric amount string should be echoed back."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "notanumber"},
        )
        assert b"notanumber" in response.data, (
            "Invalid amount string must be echoed back into the re-rendered form"
        )


# ---------------------------------------------------------------------------
# 16–18. Validation — date
# ---------------------------------------------------------------------------

class TestValidationDate:
    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",   # month 13
        "2026-00-15",   # month 0
        "2026/06/01",   # wrong separator
        "01-06-2026",   # wrong order
        "",             # empty
        "May 1 2026",   # human-readable
    ])
    def test_invalid_date_returns_200(self, auth_client, app, bad_date):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "date": bad_date},
        )
        assert response.status_code == 200, (
            f"Invalid date '{bad_date}' must re-render form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",
        "",
    ])
    def test_invalid_date_shows_error_message(self, auth_client, app, bad_date):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "date": bad_date},
        )
        decoded = response.data.decode().lower()
        assert "error" in decoded or "valid" in decoded or "date" in decoded, (
            f"A visible error message must appear for invalid date='{bad_date}'"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",
        "",
    ])
    def test_invalid_date_does_not_update_db(self, auth_client, app, bad_date):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, date_str="2026-05-01")
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "date": bad_date},
        )
        row = _get_expense(app, eid)
        assert row["date"] == "2026-05-01", (
            f"DB date must remain unchanged for invalid date='{bad_date}'"
        )

    def test_invalid_date_preserves_amount_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "42.00", "date": "bad-date"},
        )
        assert b"42.00" in response.data or b"42" in response.data, (
            "Amount must be preserved in the form after an invalid date error"
        )

    def test_invalid_date_preserves_category_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "category": "Entertainment", "date": "bad-date"},
        )
        assert b"Entertainment" in response.data, (
            "Category must be preserved in the form after an invalid date error"
        )

    def test_invalid_date_preserves_description_in_form(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        unique = "desc preserved on bad date error xyz"
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "date": "bad-date", "description": unique},
        )
        assert unique.encode() in response.data, (
            "Description must be preserved after an invalid date error"
        )


# ---------------------------------------------------------------------------
# 19. Validation — category
# ---------------------------------------------------------------------------

class TestValidationCategory:
    @pytest.mark.parametrize("bad_category", [
        "food",                             # wrong case
        "FOOD",                             # all caps
        "Groceries",                        # not in the allowed list
        "",                                 # empty string
        "random_value",
        "Food; DROP TABLE expenses;",       # SQL injection attempt
    ])
    def test_invalid_category_returns_400(self, auth_client, app, bad_category):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "category": bad_category},
        )
        assert response.status_code == 400, (
            f"Category '{bad_category}' must return 400 (not in ALLOWED_CATEGORIES)"
        )

    @pytest.mark.parametrize("bad_category", [
        "food",
        "FOOD",
        "Groceries",
        "",
        "random_value",
    ])
    def test_invalid_category_does_not_update_db(self, auth_client, app, bad_category):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, category="Food")
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "category": bad_category},
        )
        row = _get_expense(app, eid)
        assert row["category"] == "Food", (
            f"DB category must remain unchanged for invalid category='{bad_category}'"
        )

    @pytest.mark.parametrize("valid_category", [
        "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
    ])
    def test_every_allowed_category_is_accepted(self, auth_client, app, valid_category):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "category": valid_category},
        )
        assert response.status_code == 302, (
            f"Category '{valid_category}' must be accepted (redirect 302)"
        )
        row = _get_expense(app, eid)
        assert row["category"] == valid_category, (
            f"DB category must be updated to '{valid_category}'"
        )


# ---------------------------------------------------------------------------
# 20. POST no description — NULL stored in DB
# ---------------------------------------------------------------------------

class TestPostNoDescription:
    def test_blank_description_redirects(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "description": ""},
        )
        assert response.status_code == 302, (
            "POST with blank description must succeed and redirect (302)"
        )

    def test_blank_description_stores_null_in_db(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Had a description before")
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "description": ""},
        )
        row = _get_expense(app, eid)
        assert row["description"] is None, (
            "Blank description must be stored as NULL in the DB"
        )

    def test_whitespace_only_description_stores_null(self, auth_client, app):
        """Whitespace stripped to empty string must also be stored as NULL."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Some old description")
        auth_client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "description": "   "},
        )
        row = _get_expense(app, eid)
        assert row["description"] is None, (
            "Whitespace-only description must be stored as NULL"
        )


# ---------------------------------------------------------------------------
# 21. Edit link on expenses list
# ---------------------------------------------------------------------------

class TestEditLinkInExpensesList:
    def test_expenses_list_contains_edit_link(self, auth_client, app):
        """Each expense row in /profile/expenses must have an edit link."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get("/profile/expenses")
        assert response.status_code == 200, (
            "/profile/expenses must return 200 for authenticated user"
        )
        assert b"/edit" in response.data, (
            "Expenses list must contain at least one edit link"
        )

    def test_edit_link_points_to_correct_expense_url(self, auth_client, app):
        """The edit link for an expense with id N must point to /expenses/N/edit."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get("/profile/expenses")
        expected_url_fragment = f"/expenses/{eid}/edit".encode()
        assert expected_url_fragment in response.data, (
            f"Edit link for expense {eid} must contain '/expenses/{eid}/edit'"
        )

    def test_edit_link_present_for_each_expense(self, auth_client, app):
        """When multiple expenses exist, each must have a corresponding edit link."""
        uid = _get_user_id(app, "testuser@test.com")
        eids = [
            _insert_expense(app, uid, description=f"expense {i}")
            for i in range(3)
        ]
        response = auth_client.get("/profile/expenses")
        for eid in eids:
            expected = f"/expenses/{eid}/edit".encode()
            assert expected in response.data, (
                f"Edit link for expense {eid} must appear in the expenses list"
            )

    def test_edit_link_is_navigable(self, auth_client, app):
        """Following the edit link from the expenses list must return 200."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        edit_url = f"/expenses/{eid}/edit"
        response = auth_client.get(edit_url)
        assert response.status_code == 200, (
            f"Navigating to the edit link '{edit_url}' must return 200"
        )


# ---------------------------------------------------------------------------
# 22. User isolation — POST to another user's expense returns 404
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_cannot_edit_another_users_expense_via_post(self, client, app):
        """
        User B should not be able to update User A's expense even with valid data.
        The response must be 404 (not a 200 success or silent update).
        """
        # Create User A with an expense
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "isola@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_a = _get_user_id(app, "isola@test.com")
        eid = _insert_expense(app, uid_a, amount=100.00, description="User A private")

        # Switch to User B
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "isolb@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        # User B attempts to overwrite User A's expense
        response = client.post(
            f"/expenses/{eid}/edit",
            data={**VALID_EDIT_FORM, "amount": "1.00", "description": "Hacked by B"},
        )
        assert response.status_code == 404, (
            "POST to another user's expense must return 404"
        )

        # Verify the DB row was not modified
        row = _get_expense(app, eid)
        assert row["amount"] == pytest.approx(100.00), (
            "Expense amount must remain unchanged after an unauthorised edit attempt"
        )
        assert row["description"] == "User A private", (
            "Expense description must remain unchanged after an unauthorised edit attempt"
        )

    def test_user_only_sees_own_expenses_in_list(self, client, app):
        """Each user's expenses list must only show their own expenses."""
        # User A adds an expense
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "visiA@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_a = _get_user_id(app, "visiA@test.com")
        _insert_expense(app, uid_a, description="UserA only secret expense xyz")

        # User B logs in and checks their expenses list
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "visiB@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        response = client.get("/profile/expenses")
        assert b"UserA only secret expense xyz" not in response.data, (
            "User B's expenses list must not contain User A's expenses"
        )
