import json
from datetime import datetime, timezone

from export_import import build_import_preview, export_cards_json, import_cards_json
from services.time_service import local_date_iso
from storage import _fetch_all_pages


def test_json_round_trip_preserves_source_mapping_and_card_metadata() -> None:
    source_cards = [
        {
            "id": "source-1",
            "source_text": "民法【709条】",
            "title": "不法行為",
            "category": "民法",
            "card_type": "規範",
            "created_at": "2026-05-01T00:00:00Z",
        }
    ]
    cards = [
        {
            "id": "card-1",
            "source_id": "source-1",
            "question": "民法______",
            "answer": "709条",
            "title": "不法行為",
            "category": "民法",
            "card_type": "規範",
            "rank": "A+",
            "highlighted_keywords": "709条",
            "ease_factor": 2.1,
            "interval": 6,
            "repetitions": 3,
            "next_review": "2026-06-01",
            "blank_count": 2,
            "is_favorite": True,
        }
    ]

    exported = export_cards_json(cards, source_cards)
    payload = json.loads(exported)
    result = import_cards_json(exported)

    assert payload["version"] == "2.0"
    assert result["error"] is None
    assert result["source_cards"][0]["export_id"] == "source-1"
    assert result["cards"][0]["source_export_id"] == "source-1"
    assert result["cards"][0]["rank"] == "A+"
    assert result["cards"][0]["card_type"] == "規範"
    assert result["cards"][0]["highlighted_keywords"] == "709条"
    assert result["cards"][0]["ease_factor"] == 2.1
    assert result["cards"][0]["interval"] == 6
    assert result["cards"][0]["repetitions"] == 3
    assert result["cards"][0]["next_review"] == "2026-06-01"
    assert result["cards"][0]["blank_count"] == 2
    assert result["cards"][0]["is_favorite"] is True


def test_json_import_skips_duplicates_by_question_and_answer() -> None:
    exported = json.dumps(
        {
            "version": "2.0",
            "cards": [{"question": "Q", "answer": "A"}],
            "source_cards": [],
        }
    )

    result = import_cards_json(
        exported, existing_cards=[{"question": "Q", "answer": "A"}]
    )

    assert result["error"] is None
    assert result["cards"] == []
    assert result["skipped"] == 1


def test_json_import_skips_duplicate_cards_inside_same_file() -> None:
    exported = json.dumps(
        {
            "version": "2.0",
            "cards": [
                {
                    "question": "Q______",
                    "answer": "A",
                    "category": "民法",
                    "card_type": "規範",
                    "rank": "B",
                    "blank_count": 1,
                },
                {
                    "question": "Q______",
                    "answer": "A",
                    "category": "民法",
                    "card_type": "規範",
                    "rank": "B",
                    "blank_count": 1,
                },
            ],
            "source_cards": [],
        }
    )

    result = import_cards_json(exported)

    assert len(result["cards"]) == 1
    assert result["skipped"] == 1


def test_json_import_rejects_unsupported_version_and_missing_source_reference() -> None:
    unsupported = import_cards_json(json.dumps({"version": "3.0", "cards": []}))
    missing_source = import_cards_json(
        json.dumps(
            {
                "version": "2.0",
                "source_cards": [],
                "cards": [
                    {
                        "source_export_id": "missing",
                        "question": "Q______",
                        "answer": "A",
                        "category": "民法",
                        "card_type": "規範",
                        "rank": "B",
                        "blank_count": 1,
                    }
                ],
            }
        )
    )

    assert unsupported["error"]
    assert "参照先" in missing_source["error"]
    assert build_import_preview(missing_source).can_import is False


def test_json_reset_progress_matches_csv_behavior() -> None:
    exported = json.dumps(
        {
            "version": "2.0",
            "source_cards": [],
            "cards": [
                {
                    "question": "Q______",
                    "answer": "A",
                    "category": "民法",
                    "card_type": "規範",
                    "rank": "B",
                    "blank_count": 1,
                    "ease_factor": 1.5,
                    "interval": 30,
                    "repetitions": 8,
                    "next_review": "2030-01-01",
                }
            ],
        }
    )

    result = import_cards_json(exported, reset_progress=True)

    assert result["cards"][0]["ease_factor"] == 2.5
    assert result["cards"][0]["interval"] == 1
    assert result["cards"][0]["repetitions"] == 0
    assert result["cards"][0]["next_review"] == local_date_iso()


def test_fetch_all_pages_collects_more_than_one_supabase_page() -> None:
    rows = [{"id": i} for i in range(2505)]

    def fetch_page(start: int, end: int) -> list[dict[str, int]]:
        return rows[start : end + 1]

    assert _fetch_all_pages(fetch_page, page_size=1000) == rows


def test_local_date_iso_uses_japan_timezone_boundary() -> None:
    utc_before_midnight_jst = datetime(2026, 5, 27, 14, 59, tzinfo=timezone.utc)
    utc_after_midnight_jst = datetime(2026, 5, 27, 15, 0, tzinfo=timezone.utc)

    assert local_date_iso(utc_before_midnight_jst) == "2026-05-27"
    assert local_date_iso(utc_after_midnight_jst) == "2026-05-28"
