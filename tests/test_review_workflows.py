from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from application_errors import MigrationUnavailableError
from pages import review_page
from use_cases.review_workflows import complete_review


@pytest.fixture
def card() -> dict[str, object]:
    return {
        "id": "card-1",
        "ease_factor": 2.5,
        "interval": 0,
        "repetitions": 0,
        "next_review": "2026-08-01",
    }


def test_complete_review_returns_only_after_atomic_rpc_succeeds(card) -> None:
    with patch(
        "use_cases.review_workflows.complete_daily_review_atomic",
        return_value={"status": "applied"},
    ) as complete_rpc:
        outcome = complete_review("user-1", "2026-08-01", card, quality=4)

    assert outcome.status == "applied"
    assert outcome.assignment_persisted is True
    assert complete_rpc.call_args.kwargs["quality"] == 4


def test_complete_review_does_not_fallback_for_arbitrary_db_failure(card) -> None:
    with (
        patch(
            "use_cases.review_workflows.complete_daily_review_atomic",
            side_effect=RuntimeError("network down"),
        ),
        patch("use_cases.review_workflows.update_card_progress") as update_progress,
    ):
        with pytest.raises(RuntimeError, match="network down"):
            complete_review("user-1", "2026-08-01", card, quality=4)

    update_progress.assert_not_called()


def test_complete_review_uses_legacy_fallback_only_when_migration_missing(card) -> None:
    with (
        patch(
            "use_cases.review_workflows.complete_daily_review_atomic",
            side_effect=MigrationUnavailableError(),
        ),
        patch("use_cases.review_workflows.update_card_progress") as update_progress,
    ):
        outcome = complete_review("user-1", "2026-08-01", card, quality=4)

    assert outcome.assignment_persisted is False
    update_progress.assert_called_once()


def test_review_page_does_not_mutate_session_when_persistence_fails(card) -> None:
    session_state = {
        "reviewed_card_ids": [],
        "reviewed_source_ids": [],
        "reviewed_card_count": 0,
    }
    card["source_id"] = "source-1"
    with (
        patch.object(review_page.st, "session_state", session_state),
        patch.object(
            review_page,
            "complete_review",
            side_effect=RuntimeError("write failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            review_page._process_review("user-1", card, quality=4)

    assert session_state["reviewed_card_ids"] == []
    assert session_state["reviewed_source_ids"] == []
    assert session_state["reviewed_card_count"] == 0


def test_previous_days_answer_does_not_reveal_new_question() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
from unittest.mock import patch
from pages import review_page as page
card = {"id": "new", "question": "問題______", "answer": "表示前の答え",
        "next_review": "2026-11-16", "card_type": "規範"}
assignment = {"card_id": "new", "completed_at": None}
st.session_state.setdefault("quota_date", "2026-11-15")
st.session_state.setdefault("show_answer", True)
with patch.multiple(page, local_date_iso=lambda: "2026-11-16",
    load_cards=lambda _: [card], get_daily_quota_limit=lambda _: 1,
    load_daily_assignments=lambda *_: [assignment], sync_daily_assignments=lambda *_: [assignment]):
    page.render_review_page("user")
"""
    ).run()
    assert all("表示前の答え" not in item.value for item in app.markdown)
    next(button for button in app.button if button.label == "答えを見る").click().run()
    assert any("表示前の答え" in item.value for item in app.markdown)
