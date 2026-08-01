from unittest.mock import patch

import pytest

from application_errors import ValidationError
from use_cases.card_workflows import (
    import_backup_payload,
    replace_source_cards,
    save_source_with_cards,
)


def _blank_card(**overrides: object) -> dict[str, object]:
    return {
        "question": "民法______",
        "answer": "709条",
        "category": "民法",
        "card_type": "規範",
        "rank": "A",
        "blank_count": 1,
        **overrides,
    }


def test_save_source_with_cards_uses_one_transactional_rpc() -> None:
    with patch(
        "use_cases.card_workflows.save_source_bundle_rpc",
        return_value={"source_count": 1, "card_count": 1},
    ) as save_rpc:
        result = save_source_with_cards(
            "user-1",
            source_text="民法【709条】",
            title="不法行為",
            category="民法",
            card_type="規範",
            cards=[_blank_card()],
        )

    assert result.source_count == 1
    assert result.card_count == 1
    payload = save_rpc.call_args.args[1]
    assert payload["mode"] == "create"
    assert payload["cards"][0]["blank_count"] == 1


def test_save_source_with_cards_validates_all_cards_before_rpc() -> None:
    with patch("use_cases.card_workflows.save_source_bundle_rpc") as save_rpc:
        with pytest.raises(ValidationError, match="答え"):
            save_source_with_cards(
                "user-1",
                source_text="民法【709条】",
                title="不法行為",
                category="民法",
                card_type="規範",
                cards=[_blank_card(answer="")],
            )

    save_rpc.assert_not_called()


def test_replace_source_cards_delegates_existing_row_discovery_to_rpc() -> None:
    with patch(
        "use_cases.card_workflows.save_source_bundle_rpc",
        return_value={"source_count": 1, "card_count": 1},
    ) as save_rpc:
        replace_source_cards(
            "user-1",
            source_id="source-1",
            source_text="民法【709条】",
            title="不法行為",
            category="民法",
            card_type="規範",
            old_card_ids=["stale-client-id"],
            cards=[_blank_card()],
        )

    payload = save_rpc.call_args.args[1]
    assert payload["mode"] == "replace"
    assert payload["source_id"] == "source-1"


def test_import_backup_payload_calls_atomic_rpc_with_source_mapping() -> None:
    with patch(
        "use_cases.card_workflows.import_backup_atomic_rpc",
        return_value={"source_count": 1, "card_count": 1},
    ) as import_rpc:
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
                        **_blank_card(),
                        "source_export_id": "source-old",
                    }
                ],
                "skipped": 2,
                "reset_progress": True,
            },
        )

    assert result.source_count == 1
    assert result.card_count == 1
    assert result.skipped_count == 2
    assert import_rpc.call_args.kwargs["reset_progress"] is True
    assert import_rpc.call_args.kwargs["cards"][0]["source_export_id"] == "source-old"
