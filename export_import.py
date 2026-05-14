"""
エクスポート/インポートモジュール — データ変換ロジック
UIレンダリングは pages/stats_page.py に移動済み。
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Any


def export_cards_json(
    cards: list[dict[str, Any]],
    source_cards: list[dict[str, Any]] | None = None,
) -> str:
    """
    カードデータをJSON形式でエクスポート

    Args:
        cards: 暗記カードのリスト
        source_cards: 原文カードのリスト（オプション）

    Returns:
        str: JSON文字列
    """
    export_data = {
        "version": "1.0",
        "exported_at": date.today().isoformat(),
        "cards": cards,
        "source_cards": source_cards or [],
    }
    return json.dumps(export_data, ensure_ascii=False, indent=2)


def export_cards_csv(cards: list[dict[str, Any]]) -> str:
    """
    カードデータをCSV形式でエクスポート

    Args:
        cards: 暗記カードのリスト

    Returns:
        str: CSV文字列
    """
    if not cards:
        return ""

    output = io.StringIO()
    fieldnames = [
        "title",
        "category",
        "question",
        "answer",
        "ease_factor",
        "interval",
        "repetitions",
        "next_review",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for card in cards:
        writer.writerow(
            {
                "title": card.get("title", ""),
                "category": card.get("category", "その他"),
                "question": card.get("question", ""),
                "answer": card.get("answer", ""),
                "ease_factor": card.get("ease_factor", 2.5),
                "interval": card.get("interval", 1),
                "repetitions": card.get("repetitions", 0),
                "next_review": card.get("next_review", ""),
            }
        )

    return output.getvalue()


def import_cards_json(
    json_data: str,
    existing_cards: list[dict[str, Any]] | None = None,
    duplicate_action: str = "skip",
) -> dict[str, Any]:
    """
    JSONからカードデータをインポート

    Args:
        json_data: JSON文字列
        existing_cards: 既存のカードリスト（重複チェック用）
        duplicate_action: 重複時の動作 ("skip" or "create_duplicate")

    Returns:
        dict: {cards, source_cards, skipped, error}
    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        return {
            "cards": [],
            "source_cards": [],
            "skipped": 0,
            "error": f"JSON解析エラー: {e}",
        }

    cards: list[dict[str, Any]] = data.get("cards", [])
    source_cards: list[dict[str, Any]] = data.get("source_cards", [])

    # 重複チェック
    skipped = 0
    if existing_cards and duplicate_action == "skip":
        existing_set = {
            (c.get("question", ""), c.get("answer", "")) for c in existing_cards
        }
        new_cards: list[dict[str, Any]] = []
        for card in cards:
            key = (card.get("question", ""), card.get("answer", ""))
            if key not in existing_set:
                new_cards.append(card)
            else:
                skipped += 1
        cards = new_cards

    return {
        "cards": cards,
        "source_cards": source_cards,
        "skipped": skipped,
        "error": None,
    }


def import_cards_csv(
    csv_data: str,
    existing_cards: list[dict[str, Any]] | None = None,
    duplicate_action: str = "skip",
    reset_progress: bool = True,
) -> dict[str, Any]:
    """
    CSVからカードデータをインポート

    Args:
        csv_data: CSV文字列
        existing_cards: 既存のカードリスト（重複チェック用）
        duplicate_action: 重複時の動作 ("skip" or "create_duplicate")
        reset_progress: 学習進捗をリセットするか

    Returns:
        dict: {cards, skipped, error}
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        cards: list[dict[str, Any]] = []

        for row in reader:
            card: dict[str, Any] = {
                "title": row.get("title", ""),
                "category": row.get("category", "その他"),
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
            }

            if reset_progress:
                card["ease_factor"] = 2.5
                card["interval"] = 1
                card["repetitions"] = 0
                card["next_review"] = date.today().isoformat()
            else:
                card["ease_factor"] = float(row.get("ease_factor", 2.5))
                card["interval"] = int(row.get("interval", 1))
                card["repetitions"] = int(row.get("repetitions", 0))
                card["next_review"] = row.get("next_review", date.today().isoformat())

            if card["question"] and card["answer"]:
                cards.append(card)

    except Exception as e:
        return {"cards": [], "skipped": 0, "error": f"CSV解析エラー: {e}"}

    # 重複チェック
    skipped = 0
    if existing_cards and duplicate_action == "skip":
        existing_set = {
            (c.get("question", ""), c.get("answer", "")) for c in existing_cards
        }
        new_cards: list[dict[str, Any]] = []
        for card in cards:
            key = (card["question"], card["answer"])
            if key not in existing_set:
                new_cards.append(card)
            else:
                skipped += 1
        cards = new_cards

    return {"cards": cards, "skipped": skipped, "error": None}
