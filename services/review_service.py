"""
復習アルゴリズムサービス — SM-2 + ハイブリッド出題選択

元の utils.py からロジックを移行し、Type Hints・パフォーマンス改善を適用。
"""

from __future__ import annotations

import datetime
from typing import Any

from config import DEFAULT_EASE_FACTOR, MIN_EASE_FACTOR, RANK_WEIGHT
from services.time_service import local_date_iso


def calculate_next_review(quality: int, card_data: dict[str, Any]) -> dict[str, Any]:
    """
    SM-2アルゴリズムに基づく次回復習日の計算

    Args:
        quality: 回答の品質（0-5）
        card_data: 現在のカード状態

    Returns:
        dict: 更新されたカード状態
    """
    repetitions = card_data.get("repetitions", 0)
    interval = card_data.get("interval", 0)
    ease_factor = card_data.get("ease_factor", DEFAULT_EASE_FACTOR)

    if quality >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = int(interval * ease_factor)
        repetitions += 1
    else:
        repetitions = 0
        interval = 1

    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < MIN_EASE_FACTOR:
        ease_factor = MIN_EASE_FACTOR

    today = datetime.date.fromisoformat(local_date_iso())
    next_review_date = today + datetime.timedelta(days=interval)

    return {
        "repetitions": repetitions,
        "interval": interval,
        "ease_factor": ease_factor,
        "last_review": today.isoformat(),
        "next_review": next_review_date.isoformat(),
    }


def get_initial_card_state() -> dict[str, Any]:
    """新規カードの初期状態を返す"""
    return {
        "repetitions": 0,
        "interval": 0,
        "ease_factor": DEFAULT_EASE_FACTOR,
        "last_review": None,
        "next_review": local_date_iso(),
    }


def reconcile_daily_quota(
    current_quota_ids: list[str] | None,
    reviewed_card_ids: list[str],
    due_cards: list[dict[str, Any]],
    daily_limit: int,
    all_cards: list[dict[str, Any]],
) -> list[str]:
    """
    今日のノルマIDを、重複・削除済みカード・ノルマ変更に耐える形へ補正する。

    既にレビューしたカードは今日の進捗として残し、未達分だけ due カードから補充する。
    """
    available_card_ids = {_get_card_id(card) for card in all_cards}
    available_card_ids.discard(None)

    quota_ids = _normalize_card_ids(current_quota_ids, available_card_ids)
    reviewed_ids = _normalize_card_ids(reviewed_card_ids, available_card_ids)

    quota_seen = set(quota_ids)
    for card_id in reviewed_ids:
        if card_id not in quota_seen:
            quota_ids.append(card_id)
            quota_seen.add(card_id)

    if len(quota_ids) > daily_limit:
        reviewed_id_set = set(reviewed_ids)
        reviewed_quota_ids = [
            card_id for card_id in quota_ids if card_id in reviewed_id_set
        ]
        unreviewed_quota_ids = [
            card_id for card_id in quota_ids if card_id not in reviewed_id_set
        ]
        unreviewed_limit = max(0, daily_limit - len(reviewed_quota_ids))
        quota_ids = reviewed_quota_ids + unreviewed_quota_ids[:unreviewed_limit]
        quota_seen = set(quota_ids)

    remaining_slots = daily_limit - len(quota_ids)
    if remaining_slots <= 0:
        return quota_ids

    candidates = _dedupe_cards_by_id(
        [card for card in due_cards if _get_card_id(card) not in quota_seen]
    )
    additional_cards = select_hybrid_quota(candidates, remaining_slots, all_cards)

    for card in additional_cards:
        card_id = _get_card_id(card)
        if card_id is not None and card_id not in quota_seen:
            quota_ids.append(card_id)
            quota_seen.add(card_id)

    return quota_ids


# ============ ハイブリッド最適化アルゴリズム ============


def select_hybrid_quota(
    due_cards: list[dict[str, Any]],
    limit: int,
    all_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    ハイブリッド最適化によるカード選択（ランク対応・知識類型カード比率調整版）

    1. 同一source_idのカードを除外（1日1枚まで）
    2. 知識・類型カードは全体の1/5を割り当て
    3. 各グループごとに、ランク×苦手/期限を組み合わせて選出
    """
    if not due_cards:
        return []

    due_cards = _dedupe_cards_by_id(due_cards)

    # 1. 同一source_idのカードを優先的に選出（1日1枚）し、不足分は同一ソースの別カードで補充
    seen_source_ids: set[str] = set()
    primary_candidates: list[dict[str, Any]] = []
    secondary_candidates: list[dict[str, Any]] = []

    for card in due_cards:
        source_id = card.get("source_id")
        if not source_id:  # None, "" などの場合は制限せず優先候補へ
            primary_candidates.append(card)
        elif source_id not in seen_source_ids:
            seen_source_ids.add(source_id)
            primary_candidates.append(card)
        else:
            secondary_candidates.append(card)

    unique_cards = primary_candidates.copy()
    if len(unique_cards) < limit:
        needed = limit - len(unique_cards)
        unique_cards.extend(secondary_candidates[:needed])

    if len(unique_cards) <= limit:
        return unique_cards

    # 2. 知識・類型カードと一般カードに分類
    tk_cards: list[dict[str, Any]] = []
    normal_cards: list[dict[str, Any]] = []
    for c in unique_cards:
        is_tk = c.get("category") in ("知識", "類型") or c.get("card_type") in (
            "知識",
            "類型",
        )
        if is_tk:
            tk_cards.append(c)
        else:
            normal_cards.append(c)

    target_tk_count = limit // 5
    actual_tk_count = min(target_tk_count, len(tk_cards))
    actual_normal_count = min(limit - actual_tk_count, len(normal_cards))

    if actual_tk_count + actual_normal_count < limit:
        actual_tk_count = min(len(tk_cards), limit - actual_normal_count)

    selected_tk = _select_group_cards(tk_cards, actual_tk_count)
    selected_normal = _select_group_cards(normal_cards, actual_normal_count)
    selected = selected_tk + selected_normal

    # 3. 総穴埋め数を目標値に調整
    if all_cards:
        avg_blank = sum(c.get("blank_count", 1) for c in all_cards) / len(all_cards)
        target_blanks = avg_blank * limit
        selected = _adjust_to_target_blanks(
            selected, unique_cards, target_blanks, limit
        )

    return selected


def _select_group_cards(
    candidates: list[dict[str, Any]], count: int
) -> list[dict[str, Any]]:
    """グループ内のカード選択（科目均等ラウンドロビン ＋ 苦手優先・期限優先）"""
    if not candidates or count == 0:
        return []
    if len(candidates) <= count:
        return candidates

    # 1. カテゴリ（科目）ごとに分類する
    by_category: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        cat = c.get("category", "その他")
        by_category.setdefault(cat, []).append(c)

    # 2. カテゴリ内のカードを重要度・習熟度で個別に優先度順に並べる
    sorted_by_cat: dict[str, list[dict[str, Any]]] = {}
    for cat, cards in by_category.items():
        difficulty_sorted = sorted(
            cards,
            key=lambda c: (
                -RANK_WEIGHT.get(c.get("rank", "B"), 2),
                c.get("ease_factor", DEFAULT_EASE_FACTOR),
            ),
        )
        deadline_sorted = sorted(
            cards,
            key=lambda c: (
                -RANK_WEIGHT.get(c.get("rank", "B"), 2),
                c.get("next_review", "9999-99-99"),
            ),
        )

        # 苦手優先と期限優先を交互に配置
        ordered_cards: list[dict[str, Any]] = []
        seen = set()
        diff_idx = 0
        dead_idx = 0

        while len(ordered_cards) < len(cards):
            if diff_idx < len(difficulty_sorted):
                c = difficulty_sorted[diff_idx]
                diff_idx += 1
                if id(c) not in seen:
                    ordered_cards.append(c)
                    seen.add(id(c))

            if dead_idx < len(deadline_sorted):
                c = deadline_sorted[dead_idx]
                dead_idx += 1
                if id(c) not in seen:
                    ordered_cards.append(c)
                    seen.add(id(c))

        sorted_by_cat[cat] = ordered_cards

    # 3. カテゴリ間で均等にラウンドロビンで抽出する
    selected_cards: list[dict[str, Any]] = []
    category_keys = list(sorted_by_cat.keys())

    while len(selected_cards) < count and category_keys:
        for cat in list(category_keys):
            if not sorted_by_cat[cat]:
                # この科目のカードが尽きた場合は候補から外す
                category_keys.remove(cat)
                continue

            selected_cards.append(sorted_by_cat[cat].pop(0))
            if len(selected_cards) == count:
                break

    return selected_cards


def _adjust_to_target_blanks(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    target: float,
    limit: int,
) -> list[dict[str, Any]]:
    """
    総穴埋め数を目標値に近づけるよう調整
    ※同一source_idのカードが選ばれないようチェック
    """
    selected = _dedupe_cards_by_id(selected)
    candidates = _dedupe_cards_by_id(candidates)
    current_blanks = _sum_blank_count(selected)

    if abs(current_blanks - target) < 1:
        return _fill_unique_selection(selected, candidates, limit)

    def get_selected_card_ids(cards: list[dict[str, Any]]) -> set[str]:
        return {
            card_id for card in cards if (card_id := _get_card_id(card)) is not None
        }

    def get_selected_source_ids(cards: list[dict[str, Any]]) -> set[str]:
        return {c.get("source_id") for c in cards if c.get("source_id") is not None}

    for _ in range(5):
        if abs(current_blanks - target) < 1:
            break

        selected_card_ids = get_selected_card_ids(selected)
        selected_source_ids = get_selected_source_ids(selected)
        not_selected = [
            card for card in candidates if _get_card_id(card) not in selected_card_ids
        ]

        if current_blanks > target:
            high_blank_cards = sorted(
                selected, key=lambda c: c.get("blank_count", 1), reverse=True
            )
            low_blank_candidates = sorted(
                not_selected, key=lambda c: c.get("blank_count", 1)
            )

            for high_card in high_blank_cards:
                for low_card in low_blank_candidates:
                    low_card_source_id = low_card.get("source_id")
                    if (
                        low_card_source_id is not None
                        and low_card_source_id in selected_source_ids
                        and low_card_source_id != high_card.get("source_id")
                    ):
                        continue

                    if low_card.get("blank_count", 1) < high_card.get("blank_count", 1):
                        selected = _replace_selected_card(selected, high_card, low_card)
                        current_blanks = _sum_blank_count(selected)
                        break
                if abs(current_blanks - target) < 1:
                    break
        else:
            low_blank_cards = sorted(selected, key=lambda c: c.get("blank_count", 1))
            high_blank_candidates = sorted(
                not_selected, key=lambda c: c.get("blank_count", 1), reverse=True
            )

            for low_card in low_blank_cards:
                for high_card in high_blank_candidates:
                    high_card_source_id = high_card.get("source_id")
                    if (
                        high_card_source_id is not None
                        and high_card_source_id in selected_source_ids
                        and high_card_source_id != low_card.get("source_id")
                    ):
                        continue

                    if high_card.get("blank_count", 1) > low_card.get("blank_count", 1):
                        selected = _replace_selected_card(selected, low_card, high_card)
                        current_blanks = _sum_blank_count(selected)
                        break
                if abs(current_blanks - target) < 1:
                    break

    return _fill_unique_selection(selected, candidates, limit)


def _sum_blank_count(cards: list[dict[str, Any]]) -> int:
    """カード群の穴埋め数合計を返す。"""
    return sum(c.get("blank_count", 1) for c in cards)


def _replace_selected_card(
    selected: list[dict[str, Any]],
    old_card: dict[str, Any],
    new_card: dict[str, Any],
) -> list[dict[str, Any]]:
    """選定済みカードを1件入れ替え、カードIDの重複を防ぐ。"""
    new_card_id = _get_card_id(new_card)
    replaced: list[dict[str, Any]] = []

    for card in selected:
        if card is old_card:
            replaced.append(new_card)
            continue
        if _get_card_id(card) == new_card_id:
            continue
        replaced.append(card)

    return _dedupe_cards_by_id(replaced)


def _fill_unique_selection(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """選定結果を一意カードIDに正規化し、不足分を候補から補充する。"""
    filled = _dedupe_cards_by_id(selected)
    selected_ids = {
        card_id for card in filled if (card_id := _get_card_id(card)) is not None
    }

    for candidate in candidates:
        if len(filled) >= limit:
            break
        candidate_id = _get_card_id(candidate)
        if candidate_id is None or candidate_id in selected_ids:
            continue
        filled.append(candidate)
        selected_ids.add(candidate_id)

    return filled[:limit]


def _normalize_card_ids(
    card_ids: list[str] | None,
    available_card_ids: set[str | None],
) -> list[str]:
    """カードIDリストを順序維持で重複除去し、存在するカードだけに絞る。"""
    if not card_ids:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_card_id in card_ids:
        card_id = str(raw_card_id)
        if card_id in seen or card_id not in available_card_ids:
            continue
        normalized.append(card_id)
        seen.add(card_id)

    return normalized


def _dedupe_cards_by_id(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同じカードIDが複数回入っても、選定結果に重複を持ち込まない。"""
    unique_cards: list[dict[str, Any]] = []
    seen: set[str] = set()

    for card in cards:
        card_id = _get_card_id(card)
        if card_id is None or card_id in seen:
            continue
        unique_cards.append(card)
        seen.add(card_id)

    return unique_cards


def _get_card_id(card: dict[str, Any]) -> str | None:
    card_id = card.get("id")
    if card_id is None:
        return None
    return str(card_id)
