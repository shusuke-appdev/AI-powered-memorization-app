"""
エクスポート/インポートモジュール — データ変換ロジック
UIレンダリングは pages/stats_page.py に移動済み。
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from services.time_service import local_date_iso

EXPORT_SCHEMA_VERSION = "2.0"

_CSV_FIELDNAMES = [
    "title",
    "category",
    "card_type",
    "rank",
    "question",
    "answer",
    "highlighted_keywords",
    "blank_count",
    "is_favorite",
    "ease_factor",
    "interval",
    "repetitions",
    "next_review",
]


def export_cards_json(
    cards: list[dict[str, Any]],
    source_cards: list[dict[str, Any]] | None = None,
) -> str:
    """
    カードデータをJSON形式でエクスポートする。

    原文カードと暗記カードの紐づきを復元できるよう、DB上のIDは
    インポート時の対応表作成に使う export_id として保存する。
    """
    export_data = {
        "version": EXPORT_SCHEMA_VERSION,
        "exported_at": local_date_iso(),
        "source_cards": [
            _source_card_to_export_item(source_card)
            for source_card in (source_cards or [])
        ],
        "cards": [_card_to_export_item(card) for card in cards],
    }
    return json.dumps(export_data, ensure_ascii=False, indent=2)


def export_cards_csv(cards: list[dict[str, Any]]) -> str:
    """
    カードデータをCSV形式でエクスポートする。

    CSVは暗記カード単体の簡易バックアップで、原文カードとの紐づき復元は
    JSONバックアップを使う。
    """
    if not cards:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDNAMES)
    writer.writeheader()

    for card in cards:
        writer.writerow(
            {
                field: _card_to_export_item(card).get(field, "")
                for field in _CSV_FIELDNAMES
            }
        )

    return output.getvalue()


def import_cards_json(
    json_data: str,
    existing_cards: list[dict[str, Any]] | None = None,
    duplicate_action: str = "skip",
) -> dict[str, Any]:
    """
    JSONからカードデータをインポート可能な中間形式へ変換する。

    Returns:
        dict: {cards, source_cards, skipped, error, version}
    """
    if duplicate_action not in ("skip", "create_duplicate"):
        return _error_result(f"未対応の重複処理です: {duplicate_action}")

    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        return _error_result(f"JSON解析エラー: {e}")

    if not isinstance(data, dict):
        return _error_result(
            "JSON形式が不正です。ルートはオブジェクトである必要があります。"
        )

    raw_source_cards = data.get("source_cards", [])
    raw_cards = data.get("cards", [])
    if not isinstance(raw_source_cards, list) or not isinstance(raw_cards, list):
        return _error_result(
            "JSON形式が不正です。cards/source_cards は配列である必要があります。"
        )

    source_cards = [_source_card_from_import_item(item) for item in raw_source_cards]
    cards = [_card_from_import_item(item) for item in raw_cards]

    cards, skipped = _filter_duplicate_cards(cards, existing_cards, duplicate_action)

    return {
        "cards": cards,
        "source_cards": source_cards,
        "skipped": skipped,
        "error": None,
        "version": str(data.get("version", "1.0")),
    }


def import_cards_csv(
    csv_data: str,
    existing_cards: list[dict[str, Any]] | None = None,
    duplicate_action: str = "skip",
    reset_progress: bool = True,
) -> dict[str, Any]:
    """
    CSVからカードデータをインポート可能な中間形式へ変換する。

    Returns:
        dict: {cards, skipped, error}
    """
    if duplicate_action not in ("skip", "create_duplicate"):
        return {
            "cards": [],
            "skipped": 0,
            "error": f"未対応の重複処理です: {duplicate_action}",
        }

    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        cards: list[dict[str, Any]] = []

        for row in reader:
            card: dict[str, Any] = {
                "export_id": "",
                "source_export_id": "",
                "title": _as_str(row.get("title", "")),
                "category": _as_str(row.get("category", "その他")) or "その他",
                "card_type": _optional_str(row.get("card_type")),
                "rank": _as_str(row.get("rank", "B")) or "B",
                "question": _as_str(row.get("question", "")),
                "answer": _as_str(row.get("answer", "")),
                "highlighted_keywords": _as_str(row.get("highlighted_keywords", "")),
                "blank_count": _as_int(row.get("blank_count"), 1),
                "is_favorite": _as_bool(row.get("is_favorite"), False),
            }

            if reset_progress:
                card.update(_initial_progress())
            else:
                card["ease_factor"] = _as_float(row.get("ease_factor"), 2.5)
                card["interval"] = _as_int(row.get("interval"), 1)
                card["repetitions"] = _as_int(row.get("repetitions"), 0)
                card["next_review"] = (
                    _as_str(row.get("next_review", local_date_iso()))
                    or local_date_iso()
                )

            if card["question"] and (card["answer"] or card["highlighted_keywords"]):
                cards.append(card)

    except Exception as e:
        return {"cards": [], "skipped": 0, "error": f"CSV解析エラー: {e}"}

    cards, skipped = _filter_duplicate_cards(cards, existing_cards, duplicate_action)
    return {"cards": cards, "skipped": skipped, "error": None}


def _source_card_to_export_item(source_card: dict[str, Any]) -> dict[str, Any]:
    return {
        "export_id": _as_str(source_card.get("id")),
        "source_text": _as_str(source_card.get("source_text")),
        "title": _as_str(source_card.get("title")),
        "category": _as_str(source_card.get("category", "その他")) or "その他",
        "card_type": _optional_str(source_card.get("card_type")),
        "created_at": _as_str(source_card.get("created_at")),
    }


def _card_to_export_item(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "export_id": _as_str(card.get("id")),
        "source_export_id": _as_str(card.get("source_id")),
        "question": _as_str(card.get("question")),
        "answer": _as_str(card.get("answer")),
        "title": _as_str(card.get("title")),
        "category": _as_str(card.get("category", "その他")) or "その他",
        "card_type": _optional_str(card.get("card_type")),
        "rank": _as_str(card.get("rank", "B")) or "B",
        "highlighted_keywords": _as_str(card.get("highlighted_keywords")),
        "ease_factor": _as_float(card.get("ease_factor"), 2.5),
        "interval": _as_int(card.get("interval"), 1),
        "repetitions": _as_int(card.get("repetitions"), 0),
        "next_review": _as_str(card.get("next_review", local_date_iso()))
        or local_date_iso(),
        "blank_count": _as_int(card.get("blank_count"), 1),
        "is_favorite": _as_bool(card.get("is_favorite"), False),
    }


def _source_card_from_import_item(item: Any) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    export_id = _as_str(raw.get("export_id") or raw.get("id"))
    return {
        "export_id": export_id,
        "source_text": _as_str(raw.get("source_text")),
        "title": _as_str(raw.get("title")),
        "category": _as_str(raw.get("category", "その他")) or "その他",
        "card_type": _optional_str(raw.get("card_type")),
        "created_at": _as_str(raw.get("created_at")),
    }


def _card_from_import_item(item: Any) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    return {
        "export_id": _as_str(raw.get("export_id") or raw.get("id")),
        "source_export_id": _as_str(
            raw.get("source_export_id") or raw.get("source_id")
        ),
        "question": _as_str(raw.get("question")),
        "answer": _as_str(raw.get("answer")),
        "title": _as_str(raw.get("title")),
        "category": _as_str(raw.get("category", "その他")) or "その他",
        "card_type": _optional_str(raw.get("card_type")),
        "rank": _as_str(raw.get("rank", "B")) or "B",
        "highlighted_keywords": _as_str(raw.get("highlighted_keywords")),
        "ease_factor": _as_float(raw.get("ease_factor"), 2.5),
        "interval": _as_int(raw.get("interval"), 1),
        "repetitions": _as_int(raw.get("repetitions"), 0),
        "next_review": _as_str(raw.get("next_review", local_date_iso()))
        or local_date_iso(),
        "blank_count": _as_int(raw.get("blank_count"), 1),
        "is_favorite": _as_bool(raw.get("is_favorite"), False),
    }


def _filter_duplicate_cards(
    cards: list[dict[str, Any]],
    existing_cards: list[dict[str, Any]] | None,
    duplicate_action: str,
) -> tuple[list[dict[str, Any]], int]:
    skipped = 0
    if not existing_cards or duplicate_action != "skip":
        return cards, skipped

    existing_set = {
        (_as_str(c.get("question")), _as_str(c.get("answer"))) for c in existing_cards
    }
    new_cards: list[dict[str, Any]] = []
    for card in cards:
        key = (_as_str(card.get("question")), _as_str(card.get("answer")))
        if key in existing_set:
            skipped += 1
            continue
        new_cards.append(card)
    return new_cards, skipped


def _initial_progress() -> dict[str, Any]:
    return {
        "ease_factor": 2.5,
        "interval": 1,
        "repetitions": 0,
        "next_review": local_date_iso(),
    }


def _error_result(message: str) -> dict[str, Any]:
    return {
        "cards": [],
        "source_cards": [],
        "skipped": 0,
        "error": message,
        "version": None,
    }


def _as_str(value: object) -> str:
    return "" if value is None else str(value)


def _optional_str(value: object) -> str | None:
    text = _as_str(value)
    return text if text else None


def _as_int(value: object, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: object, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)
