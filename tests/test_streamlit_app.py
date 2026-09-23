from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from pages.login_page import _set_login_session

_LOGIN_SCRIPT = r"""
import pages.login_page as login_page

login_page.get_all_users = lambda: [{"id": "user-b", "username": "User B"}]
login_page.login_user_direct = lambda user_id: (True, "ログイン成功", user_id)
login_page.create_session = lambda user_id: "token-b"
login_page.show_login_page()
"""


def test_login_clears_previous_users_streamlit_state() -> None:
    app = AppTest.from_string(_LOGIN_SCRIPT).run()
    app.session_state["reviewed_source_ids"] = ["source-a"]
    app.session_state["reviewed_card_ids"] = ["card-a"]
    app.session_state["add_card_text"] = "user-a-private-text"

    login_button = next(button for button in app.button if button.label == "👤 User B")
    app = login_button.click().run()

    assert app.session_state["user_id"] == "user-b"
    assert app.session_state["username"] == "User B"
    assert "reviewed_source_ids" not in app.session_state
    assert "reviewed_card_ids" not in app.session_state
    assert "add_card_text" not in app.session_state
    assert app.session_state["_pending_cookie_action"] == {
        "action": "set",
        "name": "session_token",
        "value": "token-b",
        "max_age": 30 * 24 * 60 * 60,
    }


def test_failed_session_creation_does_not_authenticate_user() -> None:
    session_state = {
        "register_username": "User B",
        "user_id": "user-a",
        "username": "User A",
    }
    with (
        patch("pages.login_page.st.session_state", session_state),
        patch("pages.login_page.create_session", side_effect=RuntimeError("DB down")),
    ):
        with pytest.raises(RuntimeError, match="DB down"):
            _set_login_session("user-b", "User B")

    assert session_state == {
        "_pending_cookie_action": {"action": "remove", "name": "session_token"}
    }
