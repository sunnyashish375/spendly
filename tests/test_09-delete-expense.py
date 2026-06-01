"""
tests/test_09-delete-expense.py

Tests for the Delete Expense feature (Step 09).

Spec: .claude/specs/09-delete-expense.md
Routes:
  GET  /expenses/<int:id>/delete  — render confirmation page (auth required, ownership enforced)
  POST /expenses/<int:id>/delete  — permanently delete the expense, redirect to /profile/expenses

Coverage:
  1.  Auth guard — unauthenticated GET redirects to /login (302)
  2.  Auth guard — unauthenticated GET carries next param in redirect URL
  3.  Auth guard — unauthenticated POST redirects to /login (302)
  4.  Auth guard — unauthenticated POST carries next param in redirect URL
  5.  GET 404 — expense does not exist
  6.  GET 404 — expense belongs to a different user (ownership guard on GET)
  7.  GET happy path — 200, extends base.html, confirmation content present
  8.  GET — expense amount visible on confirmation page
  9.  GET — expense category visible on confirmation page
  10. GET — expense date visible on confirmation page
  11. GET — expense description visible on confirmation page
  12. GET — POST form present on confirmation page
  13. GET — "Delete" submit button present
  14. GET — Cancel link present and points to /profile/expenses
  15. POST happy path — redirects 302 to /profile/expenses
  16. POST happy path — expense row removed from DB
  17. POST — deleted expense absent from /profile/expenses list
  18. POST 404 — expense belongs to a different user (ownership re-checked on POST)
  19. POST — other expenses in DB are not deleted
  20. Expenses list — each row has a Delete link
  21. Expenses list — Delete link points to the correct /expenses/<id>/delete URL
  22. Expenses list — Delete link present for every expense when multiple exist
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

    DB_PATH is monkey-patched so every db helper uses the per-test temp file,
    preventing cross-test contamination from the real spendly.db.
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
    """Test client that has registered and is already logged in as testuser."""
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
    """Insert a single expense row directly via parameterized SQL and return its id."""
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
    """Return a single expense row as a dict, or None if not found."""
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None


def _count_expenses(app, user_id):
    """Return the total number of expense rows for a given user."""
    with app.app_context():
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        return count


# ---------------------------------------------------------------------------
# 1–4. Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_get_unauthenticated_returns_302(self, client):
        response = client.get("/expenses/1/delete")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/1/delete must redirect (302)"
        )

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/1/delete")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/1/delete must redirect to /login"
        )

    def test_get_unauthenticated_carries_next_param(self, client):
        response = client.get("/expenses/42/delete")
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2F42%2Fdelete" in location
            or "next=/expenses/42/delete" in location
        ), "Redirect to /login must carry next=/expenses/42/delete"

    def test_post_unauthenticated_returns_302(self, client):
        response = client.post("/expenses/1/delete")
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/1/delete must redirect (302)"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/1/delete")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/1/delete must redirect to /login"
        )

    def test_post_unauthenticated_carries_next_param(self, client):
        response = client.post("/expenses/7/delete")
        location = response.headers["Location"]
        assert (
            "next=%2Fexpenses%2F7%2Fdelete" in location
            or "next=/expenses/7/delete" in location
        ), "POST redirect to /login must carry next=/expenses/7/delete"


# ---------------------------------------------------------------------------
# 5–6. 404 cases
# ---------------------------------------------------------------------------

class Test404Cases:
    def test_get_nonexistent_expense_returns_404(self, auth_client):
        """An expense ID that does not exist at all must return 404."""
        response = auth_client.get("/expenses/99999/delete")
        assert response.status_code == 404, (
            "GET /expenses/99999/delete must return 404 for a non-existent expense"
        )

    def test_get_other_users_expense_returns_404(self, client, app):
        """
        An expense that exists but belongs to a different user must return 404.
        Ownership is enforced via WHERE user_id = ? in get_expense_by_id.
        """
        # Register User A and create an expense for them
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "usera_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_a = _get_user_id(app, "usera_del@test.com")
        expense_id = _insert_expense(app, uid_a)

        # Log out User A, register and log in as User B
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "userb_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        # User B tries to access the delete confirmation for User A's expense
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 404, (
            "GET for another user's expense must return 404 (ownership guard)"
        )


# ---------------------------------------------------------------------------
# 7–14. GET happy path — confirmation page content
# ---------------------------------------------------------------------------

class TestGetConfirmationPage:
    def test_get_owned_expense_returns_200(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert response.status_code == 200, (
            "Authenticated GET for an owned expense must return 200"
        )

    def test_get_extends_base_template(self, auth_client, app):
        """All pages extending base.html must include the brand name 'Spendly'."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"Spendly" in response.data, (
            "Page must extend base.html (brand name 'Spendly' expected)"
        )

    def test_get_shows_confirmation_prompt(self, auth_client, app):
        """Confirmation page must contain text indicating a destructive action."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        decoded = response.data.decode().lower()
        assert "delete" in decoded, (
            "Confirmation page must contain the word 'delete'"
        )

    def test_get_shows_expense_amount(self, auth_client, app):
        """The stored amount must be visible on the confirmation page."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, amount=123.45)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"123.45" in response.data or b"123.4" in response.data, (
            "Stored amount (123.45) must be visible on the delete confirmation page"
        )

    def test_get_shows_expense_category(self, auth_client, app):
        """The stored category must be visible on the confirmation page."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, category="Health")
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"Health" in response.data, (
            "Stored category ('Health') must be visible on the delete confirmation page"
        )

    def test_get_shows_expense_date(self, auth_client, app):
        """The stored date must be visible on the confirmation page."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, date_str="2026-04-15")
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"2026-04-15" in response.data, (
            "Stored date ('2026-04-15') must be visible on the delete confirmation page"
        )

    def test_get_shows_expense_description(self, auth_client, app):
        """The stored description must be visible on the confirmation page."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Unique delete test description xyz")
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"Unique delete test description xyz" in response.data, (
            "Stored description must be visible on the delete confirmation page"
        )

    def test_get_contains_post_form(self, auth_client, app):
        """The confirmation page must contain a form with method POST."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        decoded = response.data.decode().lower()
        assert 'method="post"' in decoded or "method='post'" in decoded, (
            "Confirmation page must contain a <form method='POST'>"
        )

    def test_get_contains_delete_submit_button(self, auth_client, app):
        """The form must contain a Delete submit button."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"Delete" in response.data, (
            "Confirmation page form must contain a 'Delete' submit button"
        )

    def test_get_contains_cancel_link(self, auth_client, app):
        """The confirmation page must contain a Cancel link."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"Cancel" in response.data, (
            "Confirmation page must contain a 'Cancel' link"
        )

    def test_get_cancel_link_points_to_expenses_list(self, auth_client, app):
        """The Cancel link must point to /profile/expenses."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert b"/profile/expenses" in response.data, (
            "Cancel link must point to /profile/expenses"
        )

    def test_get_null_description_does_not_crash_page(self, auth_client, app):
        """An expense with NULL description must still render the confirmation page."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description=None)
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert response.status_code == 200, (
            "GET delete confirmation must render 200 even when description is NULL"
        )


# ---------------------------------------------------------------------------
# 15–17. POST happy path — redirect and DB side effects
# ---------------------------------------------------------------------------

class TestPostHappyPath:
    def test_post_redirects_302(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(f"/expenses/{eid}/delete")
        assert response.status_code == 302, (
            "Valid POST to delete must redirect (302)"
        )

    def test_post_redirects_to_expenses_list(self, auth_client, app):
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.post(f"/expenses/{eid}/delete")
        assert "/profile/expenses" in response.headers["Location"], (
            "Successful POST must redirect to /profile/expenses"
        )

    def test_post_removes_expense_from_db(self, auth_client, app):
        """After a successful POST, the expense row must not exist in the DB."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        auth_client.post(f"/expenses/{eid}/delete")
        row = _get_expense(app, eid)
        assert row is None, (
            f"Expense {eid} must no longer exist in the DB after deletion"
        )

    def test_post_expense_absent_from_expenses_list(self, auth_client, app):
        """Deleted expense's distinctive content must not appear in /profile/expenses."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid, description="Very unique description to delete abcxyz")
        auth_client.post(f"/expenses/{eid}/delete")
        list_response = auth_client.get("/profile/expenses")
        assert b"Very unique description to delete abcxyz" not in list_response.data, (
            "Deleted expense must not appear in /profile/expenses after deletion"
        )

    def test_post_get_on_deleted_expense_returns_404(self, auth_client, app):
        """After deletion, attempting GET on the same ID must return 404."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        auth_client.post(f"/expenses/{eid}/delete")
        response = auth_client.get(f"/expenses/{eid}/delete")
        assert response.status_code == 404, (
            "GET on a previously deleted expense ID must return 404"
        )


# ---------------------------------------------------------------------------
# 18. POST 404 — ownership re-checked on POST
# ---------------------------------------------------------------------------

class TestPostOwnershipGuard:
    def test_post_other_users_expense_returns_404(self, client, app):
        """
        User B posting to User A's delete endpoint must return 404.
        The ownership check must happen on POST as well as GET.
        """
        # Register User A and create an expense
        client.post(
            "/register",
            data={
                "name": "Owner User",
                "email": "owner_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_owner = _get_user_id(app, "owner_del@test.com")
        expense_id = _insert_expense(app, uid_owner, amount=200.00,
                                     description="Owner private expense")

        # Switch to attacker user
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "Attacker",
                "email": "attacker_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        # Attacker attempts to delete Owner's expense
        response = client.post(f"/expenses/{expense_id}/delete")
        assert response.status_code == 404, (
            "POST to another user's expense must return 404"
        )

    def test_post_ownership_guard_does_not_delete_row(self, client, app):
        """
        An unauthorised POST must not remove the expense row from the DB.
        """
        # Register the owner and create an expense
        client.post(
            "/register",
            data={
                "name": "Owner User",
                "email": "owner2_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_owner = _get_user_id(app, "owner2_del@test.com")
        expense_id = _insert_expense(app, uid_owner, amount=99.99,
                                     description="Should survive attack")

        # Switch to attacker
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "Attacker 2",
                "email": "attacker2_del@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        client.post(f"/expenses/{expense_id}/delete")

        # The row must still exist in the DB
        row = _get_expense(app, expense_id)
        assert row is not None, (
            "Expense must remain in DB after an unauthorised delete attempt"
        )
        assert row["description"] == "Should survive attack", (
            "Expense description must be unchanged after an unauthorised delete attempt"
        )


# ---------------------------------------------------------------------------
# 19. POST — other expenses in DB are unaffected
# ---------------------------------------------------------------------------

class TestPostDoesNotAffectOtherExpenses:
    def test_delete_does_not_remove_sibling_expense(self, auth_client, app):
        """Deleting one expense must not affect any other expense row."""
        uid = _get_user_id(app, "testuser@test.com")
        eid_keep = _insert_expense(app, uid, amount=11.11, description="Keep this one")
        eid_delete = _insert_expense(app, uid, amount=22.22, description="Delete this one")

        auth_client.post(f"/expenses/{eid_delete}/delete")

        # The sibling expense must still be in the DB
        row = _get_expense(app, eid_keep)
        assert row is not None, (
            "Sibling expense must still exist in DB after unrelated deletion"
        )
        assert row["amount"] == pytest.approx(11.11), (
            "Sibling expense amount must be unchanged after unrelated deletion"
        )
        assert row["description"] == "Keep this one", (
            "Sibling expense description must be unchanged after unrelated deletion"
        )

    def test_delete_reduces_count_by_exactly_one(self, auth_client, app):
        """Deleting one expense must reduce the total count by exactly 1."""
        uid = _get_user_id(app, "testuser@test.com")
        for i in range(3):
            _insert_expense(app, uid, description=f"expense {i}")
        count_before = _count_expenses(app, uid)

        # Delete the first expense (any one of them)
        conn = get_db()
        first_eid = conn.execute(
            "SELECT id FROM expenses WHERE user_id = ? LIMIT 1", (uid,)
        ).fetchone()[0]
        conn.close()

        auth_client.post(f"/expenses/{first_eid}/delete")
        count_after = _count_expenses(app, uid)

        assert count_after == count_before - 1, (
            f"Expense count must drop by exactly 1 (was {count_before}, got {count_after})"
        )


# ---------------------------------------------------------------------------
# 20–22. Delete link in expenses list
# ---------------------------------------------------------------------------

class TestDeleteLinkInExpensesList:
    def test_expenses_list_contains_delete_link(self, auth_client, app):
        """Each expense row in /profile/expenses must have a delete link."""
        uid = _get_user_id(app, "testuser@test.com")
        _insert_expense(app, uid)
        response = auth_client.get("/profile/expenses")
        assert response.status_code == 200, (
            "/profile/expenses must return 200 for an authenticated user"
        )
        assert b"/delete" in response.data, (
            "Expenses list must contain at least one delete link"
        )

    def test_delete_link_points_to_correct_expense_url(self, auth_client, app):
        """The delete link for expense with id N must point to /expenses/N/delete."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        response = auth_client.get("/profile/expenses")
        expected_fragment = f"/expenses/{eid}/delete".encode()
        assert expected_fragment in response.data, (
            f"Delete link for expense {eid} must contain '/expenses/{eid}/delete'"
        )

    def test_delete_link_present_for_each_expense(self, auth_client, app):
        """When multiple expenses exist, each must have a corresponding delete link."""
        uid = _get_user_id(app, "testuser@test.com")
        eids = [
            _insert_expense(app, uid, description=f"expense {i}")
            for i in range(3)
        ]
        response = auth_client.get("/profile/expenses")
        for eid in eids:
            expected = f"/expenses/{eid}/delete".encode()
            assert expected in response.data, (
                f"Delete link for expense {eid} must appear in the expenses list"
            )

    def test_delete_link_is_navigable(self, auth_client, app):
        """Following the delete link from the expenses list must return 200."""
        uid = _get_user_id(app, "testuser@test.com")
        eid = _insert_expense(app, uid)
        delete_url = f"/expenses/{eid}/delete"
        response = auth_client.get(delete_url)
        assert response.status_code == 200, (
            f"Navigating to the delete confirmation link '{delete_url}' must return 200"
        )

    def test_expenses_list_does_not_show_other_users_delete_links(self, client, app):
        """
        User B's expenses list must not contain delete links for User A's expenses.
        Each user sees only their own expense rows.
        """
        # User A creates an expense
        client.post(
            "/register",
            data={
                "name": "User A",
                "email": "usera_list@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        uid_a = _get_user_id(app, "usera_list@test.com")
        eid_a = _insert_expense(app, uid_a, description="User A secret expense xyz")

        # Log out, register and log in as User B
        client.get("/logout")
        client.post(
            "/register",
            data={
                "name": "User B",
                "email": "userb_list@test.com",
                "password": "password123",
                "confirm_password": "password123",
            },
        )

        response = client.get("/profile/expenses")
        # User B must not see a delete link for User A's specific expense ID
        user_a_delete_url = f"/expenses/{eid_a}/delete".encode()
        assert user_a_delete_url not in response.data, (
            "User B's expenses list must not contain a delete link for User A's expense"
        )
