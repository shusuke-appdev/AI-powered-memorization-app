from types import SimpleNamespace
from unittest.mock import patch

import streamlit as st

from application_errors import ValidationError
from pages import add_card_page


def _set_generated_state() -> None:
    st.session_state.clear()
    st.session_state.update(
        {
            "add_card_category": "民法",
            "add_card_title": "不法行為",
            "add_card_text": "民法【709条】",
            "add_card_type": "規範",
            "add_card_rank": "A",
            "widget_key_counter": 0,
            "generated_cards": [{"question": "民法_____", "answer": "709条"}],
            "add_card_preview_q_0": "民法_____",
            "add_card_preview_a_0": "709条",
        }
    )


def test_generated_card_save_clears_preview_and_sets_one_notice() -> None:
    _set_generated_state()
    with patch.object(
        add_card_page,
        "save_source_with_cards",
        return_value=SimpleNamespace(card_count=1),
    ) as save:
        add_card_page._save_generated_cards("user-a")

    save.assert_called_once()
    assert "generated_cards" not in st.session_state
    assert not any(key.startswith("add_card_preview_") for key in st.session_state)
    assert st.session_state["add_card_notice"] == (
        "success",
        "1 枚のカードを保存しました！（原文カードも保存済み）",
    )


def test_generated_card_save_failure_keeps_preview() -> None:
    _set_generated_state()
    with patch.object(
        add_card_page,
        "save_source_with_cards",
        side_effect=ValidationError("保存できません"),
    ):
        add_card_page._save_generated_cards("user-a")

    assert len(st.session_state["generated_cards"]) == 1
    assert st.session_state["add_card_preview_q_0"] == "民法_____"
    assert st.session_state["add_card_notice"] == ("warning", "保存できません")
