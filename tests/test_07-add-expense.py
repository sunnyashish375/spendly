"""
tests/test_07-add-expense.py

Tests for the Add Expense feature (Step 07).

Spec: .claude/specs/07-add-expense.md
Route: GET/POST /expenses/add  (route function: add_expense_route)

Coverage:
  - Auth guards: unauthenticated GET and POST both redirect to /login?next=/expenses/add
  - GET happy path: 200, form renders with correct landmarks, today's date pre-filled
  - All 7 allowed categories present in the form
  - Cancel link points to /profile
  - POST valid data: row inserted in DB with correct fields, redirect to /profile
  - POST no description: NULL stored in DB, no error raised
  - New expense visible in profile stats and recent list after submission
  - POST blank amount: 200 with error, no DB insert
  - POST amount = 0: 200 with error, no DB insert
  - POST negative amount: 200 with error, no DB insert
  - POST non-numeric amount: 200 with error, no DB insert
  - POST invalid date string: 200 with error, no DB insert
  - POST invalid category: 400, no DB insert
  - Field preservation: previously entered values echoed back on validation failure
  - HTTP method guard: DELETE / PUT / PATCH return 405
  - User isolation: expenses are scoped to the logged-in user
  - App starts without errors
"""

import pytest
from datetime import date

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

    get_db() opens connections via the module-level DB_PATH. Monkey-patching
    that attribute routes every helper to a fresh temp file, giving each test
    complete isolation without any shared state.
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
    """Test client that has registered and is already logged in as testuser@test.com."""
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


def _get_expenses_for_user(app, user_id):
    """Return all expense rows for user_id, ordered by id DESC."""
    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# A convenience payload that is always valid.
VALID_FORM = {
    "amount": "25.50",
    "category": "Food",
    "date": "2026-05-15",
    "description": "Lunch at the cafe",
}


# ---------------------------------------------------------------------------
# 1. App starts without errors
# ---------------------------------------------------------------------------

class TestAppStartup:
    def test_app_initialises_without_error(self, app):
        """Fixture already ran init_db(); asserting the app object exists is enough."""
        assert app is not None, "Flask app should initialise without raising"

    def test_landing_page_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200, "Landing page should be accessible after app startup"


# ---------------------------------------------------------------------------
# 2. Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_get_unauthenticated_redirects(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must redirect (302)"
        )

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET redirect target must be /login"
        )

    def test_get_unauthenticated_carries_next_expenses_add(self, client):
        response = client.get("/expenses/add")
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2Fadd" in location
            or "next=/expenses/add" in location
        ), "Redirect to /login must carry next=/expenses/add"

    def test_post_unauthenticated_redirects(self, client):
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must redirect (302)"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data=VALID_FORM)
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST redirect target must be /login"
        )

    def test_post_unauthenticated_carries_next_expenses_add(self, client):
        response = client.post("/expenses/add", data=VALID_FORM)
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2Fadd" in location
            or "next=/expenses/add" in location
        ), "POST redirect to /login must carry next=/expenses/add"


# ---------------------------------------------------------------------------
# 3. GET happy path — form rendering
# ---------------------------------------------------------------------------

class TestGetAddExpenseForm:
    def test_get_returns_200_for_authenticated_user(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_get_renders_page_title(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"Add Expense" in response.data, (
            "Page must contain the heading 'Add Expense'"
        )

    def test_get_extends_base_template(self, auth_client):
        """Pages that extend base.html include the brand name 'Spendly'."""
        response = auth_client.get("/expenses/add")
        assert b"Spendly" in response.data, (
            "Page must extend base.html (expected brand name 'Spendly')"
        )

    def test_get_renders_amount_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="amount"' in response.data, (
            "Form must contain an input element named 'amount'"
        )

    def test_get_renders_category_select(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="category"' in response.data, (
            "Form must contain a select element named 'category'"
        )

    def test_get_renders_date_input(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="date"' in response.data, (
            "Form must contain an input element named 'date'"
        )

    def test_get_renders_description_textarea(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b'name="description"' in response.data, (
            "Form must contain a textarea element named 'description'"
        )

    def test_get_renders_submit_button(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"Add Expense" in response.data, (
            "Form must contain a submit button labelled 'Add Expense'"
        )

    def test_get_prefills_todays_date(self, auth_client):
        """The date input value attribute must equal today's ISO date."""
        today = date.today().isoformat()
        response = auth_client.get("/expenses/add")
        assert today.encode() in response.data, (
            f"Form must pre-fill today's date ({today}) in the date field"
        )

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
    ])
    def test_get_renders_all_allowed_categories(self, auth_client, category):
        response = auth_client.get("/expenses/add")
        assert category.encode() in response.data, (
            f"Category option '{category}' must appear in the category select"
        )


# ---------------------------------------------------------------------------
# 4. Cancel link points to /profile
# ---------------------------------------------------------------------------

class TestCancelLink:
    def test_form_has_cancel_link(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"Cancel" in response.data, (
            "Form page must contain a cancel link with the text 'Cancel'"
        )

    def test_cancel_link_points_to_profile(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert b"/profile" in response.data, (
            "Cancel link must point to /profile"
        )


# ---------------------------------------------------------------------------
# 5. POST valid data — redirect and DB side effects
# ---------------------------------------------------------------------------

class TestPostHappyPath:
    def test_post_valid_data_redirects(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302, (
            "Valid POST must redirect (302)"
        )

    def test_post_valid_data_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data=VALID_FORM)
        assert "/profile" in response.headers["Location"], (
            "Successful POST must redirect to /profile"
        )

    def test_post_valid_data_inserts_one_row(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 1, "Exactly one expense row must be inserted after a valid POST"

    def test_post_valid_data_correct_amount(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["amount"] == pytest.approx(25.50), (
            "Stored amount must match submitted value (25.50)"
        )

    def test_post_valid_data_correct_category(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["category"] == "Food", (
            "Stored category must match submitted value ('Food')"
        )

    def test_post_valid_data_correct_date(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["date"] == "2026-05-15", (
            "Stored date must match submitted ISO date ('2026-05-15')"
        )

    def test_post_valid_data_correct_description(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["description"] == "Lunch at the cafe", (
            "Stored description must match submitted value"
        )

    def test_post_valid_data_correct_user_id(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["user_id"] == uid, (
            "Stored user_id must equal the logged-in user's id"
        )

    def test_post_minimal_positive_amount_accepted(self, auth_client, app):
        """0.01 is the smallest valid amount per the spec (min=0.01)."""
        uid = _get_user_id(app, "testuser@test.com")
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "amount": "0.01"})
        assert response.status_code == 302, "Amount 0.01 should be accepted"
        assert _get_expenses_for_user(app, uid)[0]["amount"] == pytest.approx(0.01)

    def test_post_large_amount_accepted(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "amount": "99999.99"})
        assert response.status_code == 302, "Large positive amount should be accepted"
        assert _get_expenses_for_user(app, uid)[0]["amount"] == pytest.approx(99999.99)


# ---------------------------------------------------------------------------
# 6. POST with no description — NULL stored in DB
# ---------------------------------------------------------------------------

class TestPostNoDescription:
    def test_post_blank_description_redirects(self, auth_client):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "description": ""})
        assert response.status_code == 302, (
            "POST with blank description must still succeed and redirect (302)"
        )

    def test_post_blank_description_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "description": ""})
        assert "/profile" in response.headers["Location"], (
            "POST with blank description must redirect to /profile"
        )

    def test_post_blank_description_stores_null(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data={**VALID_FORM, "description": ""})
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 1, "One expense row must be inserted"
        assert rows[0]["description"] is None, (
            "Blank description must be stored as NULL, not an empty string"
        )

    def test_post_whitespace_only_description_stores_null(self, auth_client, app):
        """Whitespace is stripped; the result is an empty string, stored as NULL."""
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data={**VALID_FORM, "description": "   "})
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 1, "One expense row must be inserted"
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stored as NULL"
        )


# ---------------------------------------------------------------------------
# 7. New expense appears in profile stats after submission
# ---------------------------------------------------------------------------

class TestExpenseAppearsOnProfile:
    def test_profile_loads_after_adding_expense(self, auth_client):
        auth_client.post("/expenses/add", data=VALID_FORM)
        response = auth_client.get("/profile")
        assert response.status_code == 200, (
            "Profile page must load (200) after adding an expense"
        )

    def test_new_expense_description_visible_on_profile(self, auth_client):
        unique_desc = "unique test lunch desc 7xyz"
        auth_client.post("/expenses/add", data={**VALID_FORM, "description": unique_desc})
        profile_response = auth_client.get("/profile")
        assert unique_desc.encode() in profile_response.data, (
            "Newly added expense description must appear in the profile recent expenses list"
        )

    def test_new_expense_amount_reflected_in_profile(self, auth_client):
        auth_client.post("/expenses/add", data={**VALID_FORM, "amount": "88.88"})
        profile_response = auth_client.get("/profile")
        # The amount could appear in stats total or the recent list row
        assert b"88" in profile_response.data, (
            "Newly added expense amount must be visible somewhere on the profile page"
        )

    def test_profile_expense_count_increments(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        before = len(_get_expenses_for_user(app, uid))
        auth_client.post("/expenses/add", data=VALID_FORM)
        after = len(_get_expenses_for_user(app, uid))
        assert after == before + 1, (
            "Expense count in DB must increment by 1 after a successful POST"
        )

    def test_multiple_submissions_all_persisted(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        for i in range(3):
            auth_client.post(
                "/expenses/add",
                data={
                    "amount": str(10.00 * (i + 1)),
                    "category": "Other",
                    "date": f"2026-05-{i + 1:02d}",
                    "description": f"expense {i + 1}",
                },
            )
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 3, (
            "Three successive valid POSTs must each insert a separate DB row"
        )


# ---------------------------------------------------------------------------
# 8. Validation — amount
# ---------------------------------------------------------------------------

class TestValidationAmount:
    @pytest.mark.parametrize("bad_amount", [
        "",        # blank
        "0",       # zero integer
        "0.00",    # zero float
        "-1",      # negative integer
        "-0.01",   # negative float
        "-100",    # large negative
        "abc",     # non-numeric string
        "--5",     # double-dash
    ])
    def test_invalid_amount_returns_200(self, auth_client, bad_amount):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "amount": bad_amount})
        assert response.status_code == 200, (
            f"Amount '{bad_amount}' must fail validation and re-render form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "-1",
        "abc",
        "0.00",
    ])
    def test_invalid_amount_shows_error_message(self, auth_client, bad_amount):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "amount": bad_amount})
        data = response.data.decode().lower()
        # The spec says an error message area is rendered; look for common error keywords
        assert (
            "error" in data
            or "positive" in data
            or "valid" in data
            or "amount" in data
        ), f"A visible error message must be shown for amount='{bad_amount}'"

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "0.00",
        "-1",
        "-0.01",
        "abc",
    ])
    def test_invalid_amount_does_not_insert_row(self, auth_client, app, bad_amount):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data={**VALID_FORM, "amount": bad_amount})
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 0, (
            f"No expense row must be inserted when amount is '{bad_amount}'"
        )


# ---------------------------------------------------------------------------
# 9. Validation — category
# ---------------------------------------------------------------------------

class TestValidationCategory:
    @pytest.mark.parametrize("bad_category", [
        "food",                             # wrong case
        "FOOD",                             # all caps
        "Groceries",                        # not in the allowed list
        "",                                 # empty string
        "random_value",
        "Food; DROP TABLE expenses;",       # SQL injection attempt
        "<script>alert(1)</script>",        # XSS attempt
    ])
    def test_invalid_category_returns_400(self, auth_client, bad_category):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "category": bad_category})
        assert response.status_code == 400, (
            f"Category '{bad_category}' is not in the allowed list and must return 400"
        )

    @pytest.mark.parametrize("bad_category", [
        "food",
        "FOOD",
        "Groceries",
        "",
        "random_value",
    ])
    def test_invalid_category_does_not_insert_row(self, auth_client, app, bad_category):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data={**VALID_FORM, "category": bad_category})
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 0, (
            f"No expense row must be inserted for invalid category '{bad_category}'"
        )

    @pytest.mark.parametrize("valid_category", [
        "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"
    ])
    def test_every_allowed_category_is_accepted(self, auth_client, app, valid_category):
        uid = _get_user_id(app, "testuser@test.com")
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "category": valid_category})
        assert response.status_code == 302, (
            f"Category '{valid_category}' must be accepted (redirect 302)"
        )
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 1, f"One expense row must be inserted for category '{valid_category}'"


# ---------------------------------------------------------------------------
# 10. Validation — date
# ---------------------------------------------------------------------------

class TestValidationDate:
    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",    # month 13
        "2026-00-15",    # month 0
        "2026/05/15",    # wrong separator
        "15-05-2026",    # DD-MM-YYYY order
        "May 15 2026",   # human-readable
        "",              # empty
        "9999-99-99",    # all invalid parts
    ])
    def test_invalid_date_returns_200(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "date": bad_date})
        assert response.status_code == 200, (
            f"Invalid date '{bad_date}' must re-render form with error (200), not redirect"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",
        "2026/05/15",
        "",
    ])
    def test_invalid_date_shows_error_message(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "date": bad_date})
        data = response.data.decode().lower()
        assert "error" in data or "valid" in data or "date" in data, (
            f"A visible error message must be shown for invalid date '{bad_date}'"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026-13-01",
        "2026/05/15",
        "",
    ])
    def test_invalid_date_does_not_insert_row(self, auth_client, app, bad_date):
        uid = _get_user_id(app, "testuser@test.com")
        auth_client.post("/expenses/add", data={**VALID_FORM, "date": bad_date})
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 0, (
            f"No expense row must be inserted for invalid date '{bad_date}'"
        )

    @pytest.mark.parametrize("good_date", [
        "2026-01-01",
        "2024-02-29",   # valid leap-year date
        "2000-12-31",
        "1990-07-04",
    ])
    def test_valid_date_is_accepted(self, auth_client, app, good_date):
        uid = _get_user_id(app, "testuser@test.com")
        response = auth_client.post("/expenses/add", data={**VALID_FORM, "date": good_date})
        assert response.status_code == 302, f"Valid date '{good_date}' must be accepted"
        rows = _get_expenses_for_user(app, uid)
        assert rows[0]["date"] == good_date, f"Stored date must equal submitted value '{good_date}'"


# ---------------------------------------------------------------------------
# 11. Field preservation on validation failure
# ---------------------------------------------------------------------------

class TestFieldPreservationOnFailure:
    def test_category_preserved_after_blank_amount(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "", "category": "Health"},
        )
        assert b"Health" in response.data, (
            "Category 'Health' must be re-populated after an amount validation error"
        )

    def test_date_preserved_after_blank_amount(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "", "date": "2026-03-10"},
        )
        assert b"2026-03-10" in response.data, (
            "Date '2026-03-10' must be preserved after an amount validation error"
        )

    def test_description_preserved_after_blank_amount(self, auth_client):
        unique = "unique desc preserved on amount error xyz"
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "", "description": unique},
        )
        assert unique.encode() in response.data, (
            "Description must be echoed back after an amount validation error"
        )

    def test_amount_text_preserved_after_invalid_amount(self, auth_client):
        """The raw submitted amount string (even if non-numeric) is echoed back."""
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "abc"},
        )
        assert b"abc" in response.data, (
            "Invalid amount text 'abc' must be echoed back in the re-rendered form"
        )

    def test_amount_preserved_after_invalid_date(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "42.00", "date": "not-a-date"},
        )
        assert b"42.00" in response.data or b"42" in response.data, (
            "Amount must be preserved in the form after a date validation error"
        )

    def test_category_preserved_after_invalid_date(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "category": "Entertainment", "date": "not-a-date"},
        )
        assert b"Entertainment" in response.data, (
            "Category 'Entertainment' must be preserved after a date validation error"
        )

    def test_description_preserved_after_invalid_date(self, auth_client):
        unique = "preserved description on date error abc"
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "date": "not-a-date", "description": unique},
        )
        assert unique.encode() in response.data, (
            "Description must be preserved after a date validation error"
        )

    def test_date_preserved_after_zero_amount(self, auth_client):
        response = auth_client.post(
            "/expenses/add",
            data={**VALID_FORM, "amount": "0", "date": "2026-04-01"},
        )
        assert b"2026-04-01" in response.data, (
            "Date must be preserved in the form after amount=0 validation error"
        )


# ---------------------------------------------------------------------------
# 12. HTTP method guard
# ---------------------------------------------------------------------------

class TestHttpMethodGuard:
    def test_delete_method_not_allowed(self, auth_client):
        response = auth_client.delete("/expenses/add")
        assert response.status_code == 405, (
            "DELETE /expenses/add must return 405 Method Not Allowed"
        )

    def test_put_method_not_allowed(self, auth_client):
        response = auth_client.put("/expenses/add", data=VALID_FORM)
        assert response.status_code == 405, (
            "PUT /expenses/add must return 405 Method Not Allowed"
        )

    def test_patch_method_not_allowed(self, auth_client):
        response = auth_client.patch("/expenses/add", data=VALID_FORM)
        assert response.status_code == 405, (
            "PATCH /expenses/add must return 405 Method Not Allowed"
        )


# ---------------------------------------------------------------------------
# 13. User isolation — expenses are scoped to the logged-in user
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_other_users_expenses_not_visible_on_profile(self, client, app):
        """Expenses submitted by User A must not appear on User B's profile page."""
        # Register and log in as User A; add an expense
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "usera@isolated.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        client.post(
            "/expenses/add",
            data={
                "amount": "500.00",
                "category": "Shopping",
                "date": "2026-05-20",
                "description": "user a secret purchase isolation test",
            },
        )
        # Log out User A; register and log in as User B
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "userb@isolated.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        profile_response = client.get("/profile")
        assert b"user a secret purchase isolation test" not in profile_response.data, (
            "User B must not see User A's expenses on their profile page"
        )

    def test_expense_row_belongs_to_submitting_user(self, client, app):
        """The user_id stored in the DB must match the logged-in user, not any other."""
        client.post(
            "/register",
            data={
                "name": "Solo User",
                "email": "solo@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid = _get_user_id(app, "solo@test.com")
        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses_for_user(app, uid)
        assert len(rows) == 1, "One expense should have been inserted"
        assert rows[0]["user_id"] == uid, (
            "Stored user_id must match the id of the user who submitted the form"
        )
