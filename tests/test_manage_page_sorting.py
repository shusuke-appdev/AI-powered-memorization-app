from pages.manage_page import (
    _matches_type_filter,
    _normalize_display_sort_text,
    _sort_orphan_cards,
    _sort_source_cards,
)


def test_normalize_display_sort_text_for_gojuon_key() -> None:
    assert _normalize_display_sort_text("　カタカナ　ＡＢＣ　") == "かたかな abc"


def test_sort_source_cards_by_gojuon_with_title_fallback() -> None:
    source_cards = [
        {"id": "3", "title": "カキ", "source_text": "ignored"},
        {"id": "2", "title": "", "source_text": "あお"},
        {"id": "1", "title": "アイ", "source_text": "ignored"},
        {"id": "4", "title": "", "source_text": ""},
    ]

    sorted_cards = _sort_source_cards(source_cards, {}, "50音順")

    assert [card["id"] for card in sorted_cards] == ["1", "2", "3", "4"]


def test_sort_orphan_cards_by_gojuon_with_question_fallback() -> None:
    orphan_cards = [
        {"id": "3", "title": "カキ", "question": "ignored"},
        {"id": "2", "title": "", "question": "あお"},
        {"id": "1", "title": "アイ", "question": "ignored"},
    ]

    sorted_cards = _sort_orphan_cards(orphan_cards, "50音順")

    assert [card["id"] for card in sorted_cards] == ["1", "2", "3"]


def test_sort_source_cards_by_favorite_then_gojuon() -> None:
    source_cards = [
        {"id": "1", "title": "かき", "source_text": ""},
        {"id": "2", "title": "あい", "source_text": ""},
        {"id": "3", "title": "うえ", "source_text": ""},
    ]
    cards_by_source_id = {
        "1": [{"is_favorite": False}],
        "2": [{"is_favorite": True}],
        "3": [{"is_favorite": True}],
    }

    sorted_cards = _sort_source_cards(
        source_cards,
        cards_by_source_id,
        "お気に入り優先",
    )

    assert [card["id"] for card in sorted_cards] == ["2", "3", "1"]


def test_sort_source_cards_by_highest_linked_rank() -> None:
    source_cards = [
        {"id": "1", "title": "あい", "source_text": ""},
        {"id": "2", "title": "うえ", "source_text": ""},
        {"id": "3", "title": "おか", "source_text": ""},
    ]
    cards_by_source_id = {
        "1": [{"rank": "B"}, {"rank": "A+"}],
        "2": [{"rank": "A"}],
        "3": [{"rank": "C"}],
    }

    sorted_cards = _sort_source_cards(source_cards, cards_by_source_id, "重要度順")

    assert [card["id"] for card in sorted_cards] == ["1", "2", "3"]


def test_sort_orphan_cards_by_rank() -> None:
    orphan_cards = [
        {"id": "1", "title": "あい", "question": "", "rank": "B"},
        {"id": "2", "title": "うえ", "question": "", "rank": "A+"},
        {"id": "3", "title": "おか", "question": "", "rank": "C"},
    ]

    sorted_cards = _sort_orphan_cards(orphan_cards, "重要度順")

    assert [card["id"] for card in sorted_cards] == ["2", "1", "3"]


def test_sort_source_cards_by_earliest_review_date() -> None:
    source_cards = [
        {"id": "1", "title": "あい", "source_text": ""},
        {"id": "2", "title": "うえ", "source_text": ""},
        {"id": "3", "title": "おか", "source_text": ""},
    ]
    cards_by_source_id = {
        "1": [{"next_review": "2026-06-20"}],
        "2": [{"next_review": "2026-06-18"}, {"next_review": "2026-06-30"}],
    }

    sorted_cards = _sort_source_cards(
        source_cards,
        cards_by_source_id,
        "復習日が近い順",
    )

    assert [card["id"] for card in sorted_cards] == ["2", "1", "3"]


def test_sort_orphan_cards_by_review_date() -> None:
    orphan_cards = [
        {"id": "1", "title": "あい", "question": "", "next_review": "2026-06-20"},
        {"id": "2", "title": "うえ", "question": "", "next_review": "2026-06-18"},
        {"id": "3", "title": "おか", "question": "", "next_review": ""},
    ]

    sorted_cards = _sort_orphan_cards(orphan_cards, "復習日が近い順")

    assert [card["id"] for card in sorted_cards] == ["2", "1", "3"]


def test_type_filter_matches_sources_and_orphans() -> None:
    source_card = {"card_type": "規範"}
    orphan_card = {"card_type": "知識"}

    assert _matches_type_filter(source_card, "すべて") is True
    assert _matches_type_filter(orphan_card, "すべて") is True
    assert _matches_type_filter(source_card, "規範") is True
    assert _matches_type_filter(orphan_card, "規範") is False
