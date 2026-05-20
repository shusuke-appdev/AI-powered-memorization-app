"""
統計モジュール - 学習統計の計算ロジック（UI分離版）
UI表示は pages/stats_page.py に移動済み。
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Any

from config import MASTERY_THRESHOLD

# ============ 難易度判定定数 ============

_HARD_EF_THRESHOLD: float = 2.0
_HARD_EF_WITH_LOW_REPS: float = 2.5
_HARD_REPS_THRESHOLD: int = 2
_EASY_EF_THRESHOLD: float = 2.5
_EASY_REPS_THRESHOLD: int = 3


# ============ 難易度判定（共通関数） ============


def classify_difficulty(ease_factor: float, repetitions: int) -> str:
    """
    カードの難易度を分類

    Args:
        ease_factor: SM-2のEase Factor
        repetitions: 連続正解回数

    Returns:
        "easy" | "medium" | "hard"
    """
    if repetitions == 0:
        return "medium"
    if ease_factor < _HARD_EF_THRESHOLD or (
        ease_factor < _HARD_EF_WITH_LOW_REPS and repetitions < _HARD_REPS_THRESHOLD
    ):
        return "hard"
    if ease_factor >= _EASY_EF_THRESHOLD and repetitions >= _EASY_REPS_THRESHOLD:
        return "easy"
    return "medium"


# ============ 統計計算 ============


def calculate_statistics(
    cards: list[dict[str, Any]], source_cards: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    カードデータから学習統計を計算

    Args:
        cards: 暗記カードのリスト
        source_cards: 原文カードのリスト（オプション）

    Returns:
        dict: 統計データ
    """
    if not cards:
        return {
            "total_cards": 0,
            "total_source_cards": len(source_cards) if source_cards else 0,
            "mastered_cards": 0,
            "learning_cards": 0,
            "new_cards": 0,
            "due_today": 0,
            "category_stats": {},
            "difficulty_distribution": {"easy": 0, "medium": 0, "hard": 0},
            "average_ease_factor": 2.5,
            "mastery_rate": 0,
        }

    today = datetime.date.today().isoformat()

    total_cards = len(cards)
    mastered_cards = sum(
        1 for c in cards if c.get("repetitions", 0) >= MASTERY_THRESHOLD
    )
    learning_cards = sum(
        1 for c in cards if 0 < c.get("repetitions", 0) < MASTERY_THRESHOLD
    )
    new_cards = sum(1 for c in cards if c.get("repetitions", 0) == 0)
    due_today = sum(1 for c in cards if c.get("next_review", "") <= today)

    # カテゴリ別統計
    category_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "mastered": 0,
            "due": 0,
            "difficulty": {"easy": 0, "medium": 0, "hard": 0},
        }
    )

    difficulty_distribution: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    total_ease = 0.0

    for card in cards:
        category = card.get("category", "その他")
        ef = card.get("ease_factor", 2.5)
        reps = card.get("repetitions", 0)
        total_ease += ef

        category_stats[category]["total"] += 1

        if reps >= MASTERY_THRESHOLD:
            category_stats[category]["mastered"] += 1
        if card.get("next_review", "") <= today:
            category_stats[category]["due"] += 1

        # 難易度判定（共通関数を使用 — 重複排除）
        diff_level = classify_difficulty(ef, reps)
        category_stats[category]["difficulty"][diff_level] += 1
        difficulty_distribution[diff_level] += 1

    average_ease_factor = total_ease / total_cards if total_cards > 0 else 2.5

    return {
        "total_cards": total_cards,
        "total_source_cards": len(source_cards) if source_cards else 0,
        "mastered_cards": mastered_cards,
        "learning_cards": learning_cards,
        "new_cards": new_cards,
        "due_today": due_today,
        "category_stats": dict(category_stats),
        "difficulty_distribution": difficulty_distribution,
        "average_ease_factor": round(average_ease_factor, 2),
        "mastery_rate": round(mastered_cards / total_cards * 100, 1)
        if total_cards > 0
        else 0,
    }
