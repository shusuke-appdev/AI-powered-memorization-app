"""
カード生成サービス — 穴埋めカードの生成ロジック

元の gemini_client.py からカード生成ロジックを分離。
"""

from __future__ import annotations

import math
import random
import re
from typing import Any

from config import BLANKS_PER_CARD
from services.ai_service import PUNCTUATION_SET


def merge_adjacent_selections(
    phrases: list[str], selected_indices: list[int]
) -> list[list[int]]:
    """
    隣接する選択インデックスをグループ化

    Returns:
        list of lists: 隣接するインデックスのグループ [[0,1,2], [5,6], ...]
    """
    if not selected_indices:
        return []

    sorted_indices = sorted(selected_indices)
    groups: list[list[int]] = []
    current_group = [sorted_indices[0]]

    for i in range(1, len(sorted_indices)):
        prev_idx = sorted_indices[i - 1]
        curr_idx = sorted_indices[i]

        is_adjacent = True
        for j in range(prev_idx + 1, curr_idx):
            phrase_stripped = phrases[j].strip()
            if phrase_stripped and phrase_stripped not in PUNCTUATION_SET:
                is_adjacent = False
                break

        if is_adjacent:
            current_group.append(curr_idx)
        else:
            groups.append(current_group)
            current_group = [curr_idx]

    groups.append(current_group)
    return groups


def generate_cards_from_selection(
    phrases: list[str], selected_indices: list[int]
) -> list[dict[str, str]]:
    """
    選択された文節を穴埋めにしてカードを生成（隣接ブロックは結合）

    全穴埋め箇所を必ずカバーし、1カードあたり最大5箇所を穴埋めにする。
    """
    if not selected_indices:
        return []

    groups = merge_adjacent_selections(phrases, selected_indices)
    num_blanks = len(groups)

    cards: list[dict[str, str]] = []

    def build_card_from_groups(target_groups: list[list[int]]) -> dict[str, str]:
        """指定されたグループを穴埋めにしてカードを作成"""
        question_parts: list[str] = []
        answers: list[str] = []
        all_target_indices: set[int] = set()
        for g in target_groups:
            all_target_indices.update(g)

        current_answer: list[str] = []
        in_blank = False

        for i, phrase in enumerate(phrases):
            if i in all_target_indices:
                if not in_blank:
                    question_parts.append("______")
                    in_blank = True
                current_answer.append(phrase)
            else:
                if in_blank and current_answer:
                    answers.append("".join(current_answer))
                    current_answer = []
                    in_blank = False
                question_parts.append(phrase)

        if current_answer:
            answers.append("".join(current_answer))

        return {"question": "".join(question_parts), "answer": " / ".join(answers)}

    if num_blanks <= BLANKS_PER_CARD:
        cards.append(build_card_from_groups(groups))
    else:
        num_cards = math.ceil(num_blanks / BLANKS_PER_CARD)
        group_indices = list(range(num_blanks))
        random.shuffle(group_indices)

        for card_idx in range(num_cards):
            start = card_idx * BLANKS_PER_CARD
            end = min(start + BLANKS_PER_CARD, num_blanks)
            combo = sorted(group_indices[start:end])
            target_groups = [groups[i] for i in combo]
            cards.append(build_card_from_groups(target_groups))

    return cards


# ============ 旧API互換 ============


def parse_blanks_from_text(text: str) -> list[dict[str, str]]:
    """【】マーカーからカードを生成（旧方式との互換性のため残す）"""
    pattern = r"【(.+?)】"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return []

    phrases: list[str] = []
    selected_indices: list[int] = []
    last_end = 0

    for m in matches:
        if m.start() > last_end:
            before = text[last_end : m.start()]
            if before:
                phrases.append(before)

        selected_indices.append(len(phrases))
        phrases.append(m.group(1))
        last_end = m.end()

    if last_end < len(text):
        after = text[last_end:]
        if after:
            phrases.append(after)

    return generate_cards_from_selection(phrases, selected_indices)


def validate_blank_markers(text: str) -> tuple[bool, str, int]:
    """穴埋め指定の検証（旧方式との互換性）"""
    pattern = r"【(.+?)】"
    matches = re.findall(pattern, text)

    if not matches:
        return False, "穴埋め箇所が指定されていません。", 0

    return True, f"{len(matches)}箇所の穴埋めが指定されています。", len(matches)


def generate_flashcards(
    text: str, api_key: str | None = None, keywords: Any = None
) -> list[dict[str, str]] | None:
    """旧API互換のエントリーポイント"""
    is_valid, _message, _count = validate_blank_markers(text)
    if not is_valid:
        return None
    return parse_blanks_from_text(text)


def apply_highlight(text: str, keywords_input: str) -> str:
    """カードの「知識」「類型」カテゴリ向けハイライト置換処理（複数キーワード・多重置換対応）"""
    if not text or not keywords_input:
        return text

    # 全角・半角スペース、読点、カンマ、中点で分割
    keywords = [
        k.strip() for k in re.split(r"[\s、，,・]+", keywords_input) if k.strip()
    ]

    if not keywords:
        return text

    # 文字列長の降順でソート
    keywords = sorted(list(set(keywords)), key=len, reverse=True)

    escaped_keywords = [re.escape(kw) for kw in keywords]
    pattern = r"(" + "|".join(escaped_keywords) + r")"

    highlight_span = r'<span style="color: #dc2626; text-decoration: underline; font-weight: bold;">\1</span>'
    return re.sub(pattern, highlight_span, text)
