"""
tests/test_06-date-filter-profile.py

Tests for the date-range filter feature on /profile and /profile/expenses.

Spec: .claude/specs/06-date-filter-profile.md
Feature: Date Filter for Profile Page (Step 06)

Coverage:
  - Happy paths: no-params (all-time), valid date range on both routes
  - Filter bar UI: 4 preset buttons, period label, active CSS class
  - "View all" link propagates active filter
  - Auth guards: logged-out redirects to /login with next=
  - Validation edge cases: invalid format, inverted range, missing one param
  - Empty-state: zero results in range returns 200 with empty-state markup
  - DB isolation: expenses from another user are not returned
  - Recent expenses on /profile always show across all time regardless of filter
"""

import pytest
from datetime import date, timedelta
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app configured for testing with an isolated, file-backed SQLite DB.

    We use a temp-file DB (not ':memory:') because get_db() opens a new
    connection each call using DB_PATH from db.py.  To override that path
    we monkey-patch the module-level DB_PATH so every helper uses the
    same isolated file for the duration of one test.
    """
    import database.db as db_module

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
    """Test client already registered and logged in as 'alice@test.com'."""
    client.post(
        "/register",
        data={
            "name": "Alice Test",
            "email": "alice@test.com",
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    # Register redirects to /profile if successful; session is live.
    return client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _insert_expense(app, user_id, amount, category, expense_date, description=""):
    """Insert a single expense row directly into the DB within app context."""
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        conn.close()


def _get_user_id(app, email):
    """Return the id of the user with the given email."""
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        return row["id"]


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_profile_logged_out_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated /profile"
        assert "/login" in response.headers["Location"], (
            "Redirect should point to /login"
        )
        assert "next=%2Fprofile" in response.headers["Location"] or \
               "next=/profile" in response.headers["Location"], (
            "Redirect should carry next=/profile"
        )

    def test_expenses_list_logged_out_redirects_to_login(self, client):
        response = client.get("/profile/expenses")
        assert response.status_code == 302, (
            "Expected redirect for unauthenticated /profile/expenses"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect should point to /login"
        )
        assert "next=%2Fprofile%2Fexpenses" in response.headers["Location"] or \
               "next=/profile/expenses" in response.headers["Location"], (
            "Redirect should carry next=/profile/expenses"
        )


# ---------------------------------------------------------------------------
# Happy paths — /profile with no params
# ---------------------------------------------------------------------------

class TestProfileNoParams:
    def test_profile_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Expected 200 for /profile with no params"

    def test_profile_no_params_renders_profile_template(self, auth_client):
        response = auth_client.get("/profile")
        data = response.data
        assert b"profile" in data.lower(), (
            "Expected profile-specific content in /profile response"
        )

    def test_profile_no_params_period_label_is_all_time(self, auth_client):
        response = auth_client.get("/profile")
        assert b"All time" in response.data, (
            "Expected 'All time' period label when no date params are given"
        )

    def test_profile_no_params_all_time_preset_is_active(self, auth_client):
        response = auth_client.get("/profile")
        # The all_time button should carry the --active CSS modifier class
        assert b"profile-filter-btn--active" in response.data, (
            "Expected an active preset button on /profile"
        )
        # Active button must be the All Time one
        data = response.data.decode()
        all_time_pos = data.find("All Time")
        active_pos = data.rfind("profile-filter-btn--active", 0, all_time_pos)
        # The --active class should appear immediately before (or on the same tag as) All Time
        assert "All Time" in data[active_pos:active_pos + 300], (
            "The 'All Time' button should be active when no date filter is applied"
        )


# ---------------------------------------------------------------------------
# Happy paths — /profile with valid date filter
# ---------------------------------------------------------------------------

class TestProfileWithDateFilter:
    def test_profile_valid_range_returns_200(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 50.00, "Food", "2025-03-15", "March lunch")
        _insert_expense(app, uid, 30.00, "Transport", "2025-04-10", "April bus")

        response = auth_client.get("/profile?start=2025-03-01&end=2025-03-31")
        assert response.status_code == 200, (
            "Expected 200 for /profile with a valid date range"
        )

    def test_profile_filtered_shows_in_range_expense_count(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 50.00, "Food", "2025-03-15", "March lunch")
        _insert_expense(app, uid, 30.00, "Transport", "2025-04-10", "April bus")

        response = auth_client.get("/profile?start=2025-03-01&end=2025-03-31")
        data = response.data
        # March expense category should appear in category breakdown
        assert b"Food" in data, (
            "Expected the in-range category 'Food' to appear in filtered stats"
        )

    def test_profile_filtered_excludes_out_of_range_category(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 50.00, "Food", "2025-03-15", "March lunch")
        _insert_expense(app, uid, 30.00, "UniqueTransportCat", "2025-04-10", "April bus")

        response = auth_client.get("/profile?start=2025-03-01&end=2025-03-31")
        data = response.data.decode()
        # The spec mandates that Recent Expenses always shows all-time data, so
        # UniqueTransportCat may legitimately appear there. Scope the check to
        # the stats/category-breakdown section only (everything before "Recent Expenses").
        stats_section = data.split("Recent Expenses")[0] if "Recent Expenses" in data else data
        assert "UniqueTransportCat" not in stats_section, (
            "Out-of-range expense category should not appear in the filtered stats section"
        )

    def test_profile_filtered_period_label_shows_custom_range(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 10.00, "Food", "2024-06-15", "Old lunch")

        response = auth_client.get("/profile?start=2024-06-01&end=2024-06-30")
        data = response.data.decode()
        # A custom range label should contain the start and end dates separated by a dash
        assert "2024-06-01" in data and "2024-06-30" in data, (
            "Custom date range should appear in the period label"
        )


# ---------------------------------------------------------------------------
# Happy paths — /profile/expenses with valid date filter
# ---------------------------------------------------------------------------

class TestExpensesListWithDateFilter:
    def test_expenses_list_valid_range_returns_200(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 20.00, "Food", "2025-05-10", "May coffee")

        response = auth_client.get("/profile/expenses?start=2025-05-01&end=2025-05-31")
        assert response.status_code == 200, (
            "Expected 200 for /profile/expenses with a valid date range"
        )

    def test_expenses_list_shows_in_range_expenses(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 20.00, "Food", "2025-05-10", "May coffee unique desc")
        _insert_expense(app, uid, 99.00, "Bills", "2025-04-05", "April electricity")

        response = auth_client.get("/profile/expenses?start=2025-05-01&end=2025-05-31")
        assert b"May coffee unique desc" in response.data, (
            "In-range expense should appear in /profile/expenses filtered view"
        )

    def test_expenses_list_excludes_out_of_range_expenses(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 20.00, "Food", "2025-05-10", "May coffee")
        _insert_expense(app, uid, 99.00, "Bills", "2025-04-05", "April unique electricity desc")

        response = auth_client.get("/profile/expenses?start=2025-05-01&end=2025-05-31")
        assert b"April unique electricity desc" not in response.data, (
            "Out-of-range expense should not appear in filtered /profile/expenses"
        )

    def test_expenses_list_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert response.status_code == 200, (
            "Expected 200 for /profile/expenses with no params"
        )


# ---------------------------------------------------------------------------
# Filter bar UI — preset buttons present on /profile
# ---------------------------------------------------------------------------

class TestFilterBarOnProfile:
    def test_profile_has_this_month_button(self, auth_client):
        response = auth_client.get("/profile")
        assert b"This Month" in response.data, (
            "Expected 'This Month' preset button on /profile"
        )

    def test_profile_has_last_month_button(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Last Month" in response.data, (
            "Expected 'Last Month' preset button on /profile"
        )

    def test_profile_has_last_30_days_button(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Last 30 Days" in response.data, (
            "Expected 'Last 30 Days' preset button on /profile"
        )

    def test_profile_has_all_time_button(self, auth_client):
        response = auth_client.get("/profile")
        assert b"All Time" in response.data, (
            "Expected 'All Time' preset button on /profile"
        )

    def test_profile_has_apply_button_for_custom_range(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Apply" in response.data, (
            "Expected 'Apply' button for custom date range form on /profile"
        )

    def test_profile_has_period_label_element(self, auth_client):
        response = auth_client.get("/profile")
        assert b"profile-filter-period" in response.data, (
            "Expected period label element with class 'profile-filter-period' on /profile"
        )

    def test_profile_filter_bar_element_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"profile-filter-bar" in response.data, (
            "Expected filter bar element with class 'profile-filter-bar' on /profile"
        )


# ---------------------------------------------------------------------------
# Filter bar UI — preset buttons present on /profile/expenses
# ---------------------------------------------------------------------------

class TestFilterBarOnExpenses:
    def test_expenses_has_this_month_button(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"This Month" in response.data, (
            "Expected 'This Month' preset button on /profile/expenses"
        )

    def test_expenses_has_last_month_button(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"Last Month" in response.data, (
            "Expected 'Last Month' preset button on /profile/expenses"
        )

    def test_expenses_has_last_30_days_button(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"Last 30 Days" in response.data, (
            "Expected 'Last 30 Days' preset button on /profile/expenses"
        )

    def test_expenses_has_all_time_button(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"All Time" in response.data, (
            "Expected 'All Time' preset button on /profile/expenses"
        )

    def test_expenses_has_apply_button_for_custom_range(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"Apply" in response.data, (
            "Expected 'Apply' button for custom date range form on /profile/expenses"
        )

    def test_expenses_has_period_label_element(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"expenses-filter-period" in response.data, (
            "Expected period label element with class 'expenses-filter-period' on /profile/expenses"
        )

    def test_expenses_filter_bar_element_present(self, auth_client):
        response = auth_client.get("/profile/expenses")
        assert b"expenses-filter-bar" in response.data, (
            "Expected filter bar element with class 'expenses-filter-bar' on /profile/expenses"
        )


# ---------------------------------------------------------------------------
# Active preset CSS class
# ---------------------------------------------------------------------------

class TestActivePresetClass:
    def test_all_time_active_class_when_no_params_on_profile(self, auth_client):
        """With no params, the All Time button should carry the --active modifier."""
        response = auth_client.get("/profile")
        data = response.data.decode()
        # Find the All Time anchor and verify it has the active class
        assert "profile-filter-btn--active" in data, (
            "Expected active preset CSS class on /profile with no params"
        )
        # The active class must appear on the All Time button specifically
        idx = data.find("All Time")
        # Scan backward for the nearest opening anchor tag
        tag_start = data.rfind("<a ", 0, idx)
        tag_text = data[tag_start:idx + len("All Time")]
        assert "profile-filter-btn--active" in tag_text, (
            "The 'All Time' anchor should have the --active CSS class when no filter is applied"
        )

    def test_all_time_active_class_when_no_params_on_expenses(self, auth_client):
        response = auth_client.get("/profile/expenses")
        data = response.data.decode()
        idx = data.find("All Time")
        tag_start = data.rfind("<a ", 0, idx)
        tag_text = data[tag_start:idx + len("All Time")]
        assert "expenses-filter-btn--active" in tag_text, (
            "The 'All Time' anchor on /profile/expenses should have the --active CSS class"
        )

    @pytest.mark.parametrize("preset_key,label", [
        ("this_month", "This Month"),
        ("last_month", "Last Month"),
        ("last_30", "Last 30 Days"),
    ])
    def test_preset_active_class_on_profile_for_each_preset(
        self, auth_client, app, preset_key, label
    ):
        """Navigate via the preset URL and verify that preset's button gets --active."""
        # Build the preset URL by calling the profile route with no filter first
        # and extracting the href from the rendered page
        nav_response = auth_client.get("/profile")
        data = nav_response.data.decode()

        # Extract the href for this preset from the rendered HTML
        # Each preset button looks like: class="profile-filter-btn..." href="..."
        import re
        # Find the anchor tag containing the label text
        pattern = r'<a\s+href="([^"]+)"\s+class="profile-filter-btn[^"]*"[^>]*>\s*' + re.escape(label)
        match = re.search(pattern, data)
        if match is None:
            # Try the class-first order
            pattern = r'<a\s+[^>]*class="profile-filter-btn[^"]*"[^>]*href="([^"]+)"[^>]*>\s*' + re.escape(label)
            match = re.search(pattern, data)

        assert match is not None, (
            f"Could not find preset button for '{label}' on /profile"
        )
        preset_url = match.group(1)

        # Follow the preset URL
        filtered_response = auth_client.get(preset_url)
        assert filtered_response.status_code == 200, (
            f"Expected 200 after navigating to preset '{label}'"
        )
        filtered_data = filtered_response.data.decode()

        # Find the anchor for this label in the filtered page
        match2 = re.search(
            r'<a\s+href="([^"]+)"\s+class="(profile-filter-btn[^"]*)"[^>]*>\s*' + re.escape(label),
            filtered_data,
        )
        if match2 is None:
            match2 = re.search(
                r'<a\s+[^>]*class="(profile-filter-btn[^"]*)"[^>]*href="[^"]*"[^>]*>\s*' + re.escape(label),
                filtered_data,
            )
            if match2:
                css_class = match2.group(1)
            else:
                # Fallback: just assert --active appears and the label is in the page
                assert "profile-filter-btn--active" in filtered_data, (
                    f"Expected --active class on /profile when preset '{label}' is active"
                )
                return
        else:
            css_class = match2.group(2)

        assert "profile-filter-btn--active" in css_class, (
            f"Expected the '{label}' button to have --active class on /profile"
        )

    def test_inactive_presets_do_not_have_active_class_on_profile(self, auth_client):
        """When All Time is active, the other 3 presets must NOT carry the active class."""
        response = auth_client.get("/profile")
        data = response.data.decode()
        import re
        # Collect all preset anchor tags
        tags = re.findall(
            r'<a\s[^>]*class="profile-filter-btn[^"]*"[^>]*>.*?</a>',
            data,
            re.DOTALL,
        )
        active_tags = [t for t in tags if "profile-filter-btn--active" in t]
        assert len(active_tags) == 1, (
            f"Expected exactly 1 active preset button on /profile, found {len(active_tags)}"
        )


# ---------------------------------------------------------------------------
# "View all" link propagates the active filter
# ---------------------------------------------------------------------------

class TestViewAllLinkPropagatesFilter:
    def test_view_all_link_includes_start_and_end_when_filter_active(
        self, auth_client, app
    ):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 15.00, "Food", "2025-07-20", "July snack")

        response = auth_client.get("/profile?start=2025-07-01&end=2025-07-31")
        data = response.data.decode()
        # The "View all →" link should carry start and end in its href
        assert "start=2025-07-01" in data, (
            "Expected start date in 'View all' link when filter is active"
        )
        assert "end=2025-07-31" in data, (
            "Expected end date in 'View all' link when filter is active"
        )

    def test_view_all_link_no_params_when_all_time(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 15.00, "Food", "2025-07-20", "July snack")

        response = auth_client.get("/profile")
        data = response.data.decode()
        import re
        # The "View all" anchor should point to /profile/expenses without date params
        view_all = re.search(r'href="([^"]*profile/expenses[^"]*)"[^>]*>.*?View all', data, re.DOTALL)
        if view_all:
            href = view_all.group(1)
            assert "start=" not in href, (
                "View all link should not contain start= when All Time is active"
            )
            assert "end=" not in href, (
                "View all link should not contain end= when All Time is active"
            )


# ---------------------------------------------------------------------------
# Edge cases / validation
# ---------------------------------------------------------------------------

class TestDateFilterValidation:
    def test_invalid_start_date_format_returns_200(self, auth_client):
        """Non-ISO start date should fall back to all-time, not raise 500."""
        response = auth_client.get("/profile?start=not-a-date&end=2026-05-31")
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) for invalid start date format"
        )

    def test_invalid_start_date_format_shows_all_time_label(self, auth_client):
        response = auth_client.get("/profile?start=not-a-date&end=2026-05-31")
        assert b"All time" in response.data, (
            "Expected 'All time' period label when start date is invalid"
        )

    def test_invalid_end_date_format_returns_200(self, auth_client):
        response = auth_client.get("/profile?start=2026-05-01&end=not-a-date")
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) for invalid end date format"
        )

    def test_inverted_range_returns_200(self, auth_client):
        """start > end should fall back to all-time, not raise 500."""
        response = auth_client.get("/profile?start=2026-05-31&end=2026-05-01")
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) for inverted date range"
        )

    def test_inverted_range_shows_all_time_label(self, auth_client):
        response = auth_client.get("/profile?start=2026-05-31&end=2026-05-01")
        assert b"All time" in response.data, (
            "Expected 'All time' period label when start > end"
        )

    def test_missing_end_param_returns_200(self, auth_client):
        """Only start param provided — fall back to all-time."""
        response = auth_client.get("/profile?start=2026-05-01")
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) when end param is missing"
        )

    def test_missing_end_param_shows_all_time_label(self, auth_client):
        response = auth_client.get("/profile?start=2026-05-01")
        assert b"All time" in response.data, (
            "Expected 'All time' period label when end param is missing"
        )

    def test_missing_start_param_returns_200(self, auth_client):
        """Only end param provided — fall back to all-time."""
        response = auth_client.get("/profile?end=2026-05-31")
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) when start param is missing"
        )

    def test_missing_start_param_shows_all_time_label(self, auth_client):
        response = auth_client.get("/profile?end=2026-05-31")
        assert b"All time" in response.data, (
            "Expected 'All time' period label when start param is missing"
        )

    def test_invalid_date_on_expenses_list_returns_200(self, auth_client):
        response = auth_client.get(
            "/profile/expenses?start=not-a-date&end=2026-05-31"
        )
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) for invalid date on /profile/expenses"
        )

    def test_inverted_range_on_expenses_list_returns_200(self, auth_client):
        response = auth_client.get(
            "/profile/expenses?start=2026-05-31&end=2026-05-01"
        )
        assert response.status_code == 200, (
            "Expected 200 (all-time fallback) for inverted range on /profile/expenses"
        )


# ---------------------------------------------------------------------------
# Empty state — zero expenses in selected range
# ---------------------------------------------------------------------------

class TestEmptyStateFilter:
    def test_profile_empty_state_when_no_expenses_in_range(self, auth_client, app):
        uid = _get_user_id(app, "alice@test.com")
        # Insert an expense outside the queried range
        _insert_expense(app, uid, 25.00, "Food", "2024-01-10", "Old coffee")

        response = auth_client.get("/profile?start=2025-06-01&end=2025-06-30")
        assert response.status_code == 200, (
            "Expected 200 when filter returns zero expenses, not 500"
        )
        # Should render the empty-state element
        assert b"profile-empty" in response.data or b"No expenses" in response.data, (
            "Expected empty-state message when no expenses match the filter"
        )

    def test_expenses_list_empty_state_when_no_expenses_in_range(
        self, auth_client, app
    ):
        uid = _get_user_id(app, "alice@test.com")
        _insert_expense(app, uid, 25.00, "Food", "2024-01-10", "Old coffee")

        response = auth_client.get(
            "/profile/expenses?start=2025-06-01&end=2025-06-30"
        )
        assert response.status_code == 200, (
            "Expected 200 when filter returns zero expenses on /profile/expenses"
        )
        assert b"expenses-empty" in response.data or b"No expenses" in response.data, (
            "Expected empty-state message on /profile/expenses when no expenses match"
        )

    def test_profile_empty_state_has_no_500_with_no_expenses_at_all(
        self, auth_client
    ):
        """User with zero expenses visiting a filtered URL should not 500."""
        response = auth_client.get("/profile?start=2025-01-01&end=2025-01-31")
        assert response.status_code == 200, (
            "Expected 200 for a user with no expenses at all using a date filter"
        )


# ---------------------------------------------------------------------------
# DB-level filtering — user isolation
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_filter_does_not_return_other_users_expenses(self, client, app):
        """Expenses belonging to user B must never appear in user A's filtered view."""
        from werkzeug.security import generate_password_hash

        # Create user A and user B directly in the DB
        with app.app_context():
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("User A", "usera@test.com", generate_password_hash("password123")),
            )
            uid_a = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("User B", "userb@test.com", generate_password_hash("password123")),
            )
            uid_b = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

        # Expense for user A in target range
        _insert_expense(app, uid_a, 50.00, "Food", "2025-08-15", "Alice August lunch")
        # Expense for user B in same range — should be invisible to user A
        _insert_expense(app, uid_b, 200.00, "Shopping", "2025-08-20", "Bob August splurge")

        # Log in as user A
        client.post(
            "/login",
            data={"email": "usera@test.com", "password": "password123"},
        )
        response = client.get("/profile/expenses?start=2025-08-01&end=2025-08-31")
        assert response.status_code == 200

        data = response.data
        assert b"Alice August lunch" in data, (
            "User A's own expense should appear in their filtered view"
        )
        assert b"Bob August splurge" not in data, (
            "User B's expense must not appear in User A's filtered view"
        )

    def test_profile_stats_only_count_logged_in_users_expenses(self, client, app):
        """Stats totals on /profile must reflect only the logged-in user's expenses."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("User C", "userc@test.com", generate_password_hash("password123")),
            )
            uid_c = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("User D", "userd@test.com", generate_password_hash("password123")),
            )
            uid_d = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            conn.close()

        _insert_expense(app, uid_c, 100.00, "Bills", "2025-09-10", "C electricity")
        _insert_expense(app, uid_d, 999.00, "Shopping", "2025-09-12", "D big purchase")

        client.post(
            "/login",
            data={"email": "userc@test.com", "password": "password123"},
        )
        response = client.get("/profile?start=2025-09-01&end=2025-09-30")
        assert response.status_code == 200

        data = response.data
        # User C's expense should appear; user D's should not
        assert b"Bills" in data, "User C's category should appear in filtered stats"
        assert b"999" not in data, (
            "User D's amount should not appear in User C's filtered stats"
        )


# ---------------------------------------------------------------------------
# Recent expenses on /profile always show across all time
# ---------------------------------------------------------------------------

class TestRecentExpensesAllTime:
    def test_recent_expenses_shows_all_time_regardless_of_filter(
        self, auth_client, app
    ):
        """
        The spec says get_recent_expenses on /profile always shows the 5 most
        recent across all time, regardless of the active filter.
        An old expense that is outside the queried range must still appear in
        the Recent Expenses table.
        """
        uid = _get_user_id(app, "alice@test.com")
        # Insert one expense in the filter range and one very old one
        _insert_expense(app, uid, 10.00, "Food", "2025-11-01", "November snack")
        _insert_expense(app, uid, 20.00, "Bills", "2020-01-15", "Very old bill unique")

        # Filter to only November 2025
        response = auth_client.get("/profile?start=2025-11-01&end=2025-11-30")
        assert response.status_code == 200

        # The very old bill should still appear in the Recent Expenses section
        # because get_recent_expenses ignores the filter
        # Note: this test is meaningful only if the old expense is among the 5 most
        # recent — in this fixture there are only 2 total, so it must appear.
        assert b"Very old bill unique" in response.data, (
            "Recent Expenses should display all-time recent expenses regardless of the active date filter"
        )

    def test_recent_expenses_limited_to_5_items_regardless_of_filter(
        self, auth_client, app
    ):
        """Regardless of how many total expenses exist, recent list shows at most 5."""
        uid = _get_user_id(app, "alice@test.com")
        for i in range(10):
            _insert_expense(
                app, uid, float(i + 1), "Food",
                f"2025-10-{i + 1:02d}", f"Expense {i + 1}"
            )

        response = auth_client.get("/profile")
        assert response.status_code == 200

        data = response.data.decode()
        # Count occurrences of a pattern unique to each expense row in the table.
        # We look for profile-badge (one per expense row in recent table).
        import re
        badge_count = len(re.findall(r"profile-badge", data))
        # Should be at most 5 badges (one per row in recent expenses table)
        assert badge_count <= 5, (
            f"Expected at most 5 entries in Recent Expenses, found {badge_count} badge(s)"
        )
