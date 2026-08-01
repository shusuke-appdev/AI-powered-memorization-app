from unittest.mock import patch

import pytest

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
