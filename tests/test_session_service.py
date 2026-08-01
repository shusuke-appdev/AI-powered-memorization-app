from services.session_service import reset_user_session_state


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

    assert state == {"cookie_controller": controller, "dark_mode": True}
