from unittest.mock import Mock, patch

import pytest

from use_cases.card_workflows import (
    import_backup_payload,
    replace_source_cards,
    save_source_with_cards,
)


def test_save_source_with_cards_rolls_back_created_rows_on_card_failure() -> None:
    with (
        patch("use_cases.card_workflows.add_source_card", return_value="source-new"),
        patch(
            "use_cases.card_workflows.add_card",
            side_effect=["card-1", RuntimeError("boom")],
        ),
        patch("use_cases.card_workflows.delete_card") as delete_card,
        patch("use_cases.card_workflows.delete_source_card") as delete_source_card,
    ):
        with pytest.raises(RuntimeError):
            save_source_with_cards(
                "user-1",
                source_text="source",
                title="title",
                category="民法",
                card_type="規範",
                cards=[
                    {"question": "Q1", "answer": "A1"},
                    {"question": "Q2", "answer": "A2"},
                ],
            )

    delete_card.assert_called_once_with("user-1", "card-1")
    delete_source_card.assert_called_once_with("user-1", "source-new")


def test_replace_source_cards_keeps_old_cards_when_new_card_creation_fails() -> None:
    with (
        patch("use_cases.card_workflows.add_card", side_effect=RuntimeError("boom")),
        patch("use_cases.card_workflows.delete_cards_batch") as delete_cards_batch,
        patch("use_cases.card_workflows.update_source_card") as update_source_card,
    ):
        with pytest.raises(RuntimeError):
            replace_source_cards(
                "user-1",
                source_id="source-1",
                source_text="source",
                title="title",
                category="民法",
                card_type="規範",
                old_card_ids=["old-1"],
                cards=[{"question": "Q", "answer": "A"}],
            )

    delete_cards_batch.assert_not_called()
    update_source_card.assert_not_called()


def test_import_backup_payload_maps_export_source_id_to_new_source_id() -> None:
    add_card = Mock(return_value="card-new")
    with (
        patch("use_cases.card_workflows.add_source_card", return_value="source-new"),
        patch("use_cases.card_workflows.add_card", add_card),
    ):
        result = import_backup_payload(
            "user-1",
            {
                "source_cards": [
                    {
                        "export_id": "source-old",
                        "source_text": "source",
                        "title": "title",
                        "category": "民法",
                        "card_type": "規範",
                    }
                ],
                "cards": [
                    {
                        "source_export_id": "source-old",
                        "question": "Q",
                        "answer": "A",
                        "rank": "A",
                        "card_type": "規範",
                        "ease_factor": 2.3,
                        "interval": 4,
                        "repetitions": 2,
                        "next_review": "2026-06-01",
                    }
                ],
                "skipped": 0,
            },
        )

    assert result.source_count == 1
    assert result.card_count == 1
    assert add_card.call_args.kwargs["source_id"] == "source-new"
    assert add_card.call_args.kwargs["rank"] == "A"
    assert add_card.call_args.kwargs["ease_factor"] == 2.3
