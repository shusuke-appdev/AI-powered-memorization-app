from services.session_service import (
    flush_pending_cookie_action,
    queue_cookie_remove,
    queue_cookie_set,
    reset_user_session_state,
)


def test_reset_user_session_state_removes_all_user_data() -> None:
    controller = object()
    state = {
        "cookie_controller": controller,
        "dark_mode": True,
        "user_id": "user-a",
        "username": "A",
        "reviewed_source_ids": ["source-a"],
        "reviewed_card_ids": ["card-a"],
        "add_card_text": "secret",
    }

    reset_user_session_state(state)

    assert state == {"cookie_controller": controller}


class FakeCookieController:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def set(self, name: str, value: str, *, max_age: int) -> None:
        self.calls.append(("set", name, value, max_age))

    def remove(self, name: str) -> None:
        self.calls.append(("remove", name))


def test_pending_cookie_action_is_flushed_once() -> None:
    state: dict = {}
    controller = FakeCookieController()
    queue_cookie_set(state, "session_token", "token", max_age=30)

    assert flush_pending_cookie_action(state, controller) is True
    assert flush_pending_cookie_action(state, controller) is False
    assert controller.calls == [("set", "session_token", "token", 30)]

    queue_cookie_remove(state, "session_token")
    assert flush_pending_cookie_action(state, controller) is True
    assert controller.calls[-1] == ("remove", "session_token")
