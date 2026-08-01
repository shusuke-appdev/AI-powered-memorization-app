from streamlit.testing.v1 import AppTest

_LOGIN_SCRIPT = r"""
from unittest.mock import patch

from pages.login_page import show_login_page


class FakeCookieController:
    def set(self, *args, **kwargs):
        pass


with (
    patch(
        "pages.login_page.get_all_users",
        return_value=[{"id": "user-b", "username": "User B"}],
    ),
    patch(
        "pages.login_page.login_user_direct",
        return_value=(True, "ログイン成功", "user-b"),
    ),
    patch("pages.login_page.create_session", return_value="token-b"),
):
    show_login_page(FakeCookieController())
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
