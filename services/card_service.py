"""
カード生成サービス — 穴埋めカードの生成ロジック
"""

from __future__ import annotations

import re
from typing import Any

from config import BLANKS_PER_CARD
from services.html_rendering import escape_html

HIGHLIGHT_OPEN = "【"
HIGHLIGHT_CLOSE = "】"
_HIGHLIGHT_SPAN_START = (
    '<span style="color: #dc2626; text-decoration: underline; font-weight: bold;">'
)

PUNCTUATION_SET: frozenset[str] = frozenset(
    {
        "。",
        "、",
        "，",
        "．",
        ",",
        ".",
        "！",
        "？",
        "!",
        "?",
        "：",
        ":",
        "；",
        ";",
        "「",
        "」",
        "（",
        "）",
        "(",
        ")",
    }
)


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
) -> list[dict[str, Any]]:
    """
    ユーザーが選択した文節のみを穴埋めにしてカードを生成する。

    穴埋め箇所はユーザー指定のもののみを使用し、アルゴリズム側で
    勝手に穴埋め箇所を追加することは一切しない。

    - 穴埋め箇所が5個以下: 指定された穴埋め箇所のみでカード1枚を生成
    - 穴埋め箇所が6個以上: ceil(N/5)枚のカードを生成し、各カードに
      ユーザー指定の穴埋め箇所から5箇所ずつ割り当てる。
      最後のカードが5箇所未満になる場合は、他のカードに割り当て済みの
      穴埋め箇所からランダムに補充し、必ず5箇所にする（カード間の重複は許容）。
    """
    if not selected_indices:
        return []

    groups = merge_adjacent_selections(phrases, selected_indices)
    num_blanks = len(groups)

    cards: list[dict[str, Any]] = []

    def build_card_from_groups(target_groups: list[list[int]]) -> dict[str, Any]:
        """指定されたグループを穴埋めにしてカードを作成"""
        question_parts: list[str] = []
        answers: list[str] = []

        idx_to_group: dict[int, int] = {}
        for group_idx, g in enumerate(target_groups):
            for idx in g:
                idx_to_group[idx] = group_idx

        current_answer: list[str] = []
        current_group_idx = -1

        for i, phrase in enumerate(phrases):
            if i in idx_to_group:
                g_idx = idx_to_group[i]
                if g_idx != current_group_idx:
                    if current_group_idx != -1:
                        answers.append("".join(current_answer))
                        current_answer = []
                    question_parts.append("______")
                    current_group_idx = g_idx
                current_answer.append(phrase)
            else:
                if current_group_idx != -1:
                    answers.append("".join(current_answer))
                    current_answer = []
                    current_group_idx = -1
                question_parts.append(phrase)

        if current_group_idx != -1:
            answers.append("".join(current_answer))

        return {
            "question": "".join(question_parts),
            "answer": " / ".join(answers),
            "blank_count": len(target_groups),
        }

    if num_blanks <= BLANKS_PER_CARD:
        # 穴埋め箇所が5個以下: ユーザー指定の穴埋め箇所のみで1枚生成
        cards.append(build_card_from_groups(groups))
    else:
        # 穴埋め箇所が6個以上: 各カード5箇所ずつ割り当て
        group_indices = list(range(num_blanks))
        for start in range(0, num_blanks, BLANKS_PER_CARD):
            end = min(start + BLANKS_PER_CARD, num_blanks)
            card_group_indices = group_indices[start:end]

            # 最後のカードが5箇所未満の場合、先頭側から決定的に重複補充
            if len(card_group_indices) < BLANKS_PER_CARD:
                other_indices = [
                    gi for gi in group_indices if gi not in card_group_indices
                ]
                supplement = other_indices[: BLANKS_PER_CARD - len(card_group_indices)]
                card_group_indices = card_group_indices + supplement

            card_group_indices_sorted = sorted(card_group_indices)
            target_groups = [groups[i] for i in card_group_indices_sorted]
            cards.append(build_card_from_groups(target_groups))

    return cards


def contains_highlight_markers(text: str) -> bool:
    """ハイライト用の【】マーカーが本文に含まれるかを返す。"""
    return HIGHLIGHT_OPEN in text or HIGHLIGHT_CLOSE in text


def validate_highlight_markers(text: str) -> tuple[bool, str, int]:
    """知識・類型カード用の【】ハイライト指定を検証する。"""
    if not contains_highlight_markers(text):
        return True, "ハイライト指定はありません。", 0

    return _validate_markers(text, label="ハイライト")


def _validate_markers(text: str, *, label: str) -> tuple[bool, str, int]:
    """【】マーカーを入れ子・空・片側だけの指定を含めて検証する。"""

    in_marker = False
    marker_chars: list[str] = []
    marker_count = 0

    for char in text:
        if char == HIGHLIGHT_OPEN:
            if in_marker:
                return False, f"{label}指定の中に別の【があります。", marker_count
            in_marker = True
            marker_chars = []
            continue

        if char == HIGHLIGHT_CLOSE:
            if not in_marker:
                return False, "】に対応する【がありません。", marker_count
            if not "".join(marker_chars).strip():
                return False, f"空の{label}指定があります。", marker_count
            in_marker = False
            marker_count += 1
            marker_chars = []
            continue

        if in_marker:
            marker_chars.append(char)

    if in_marker:
        return False, "【に対応する】がありません。", marker_count

    return True, f"{marker_count}箇所の{label}が指定されています。", marker_count


def extract_highlight_keywords(text: str) -> str:
    """本文内の【】マーカーから保存用のハイライト語句を抽出する。"""
    is_valid, _message, _count = validate_highlight_markers(text)
    if not is_valid:
        return ""

    keywords: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"【([^【】]+)】", text):
        keyword = match.group(1).strip()
        if keyword and keyword not in seen:
            keywords.append(keyword)
            seen.add(keyword)
    return " ".join(keywords)


def _highlight_span(text: str) -> str:
    return f"{_HIGHLIGHT_SPAN_START}{escape_html(text)}</span>"


def _apply_marker_highlight(text: str) -> str:
    highlighted_parts: list[str] = []
    last_end = 0
    for match in re.finditer(r"【([^【】]+)】", text):
        highlighted_parts.append(escape_html(text[last_end : match.start()]))
        highlighted_parts.append(_highlight_span(match.group(1)))
        last_end = match.end()

    highlighted_parts.append(escape_html(text[last_end:]))
    return "".join(highlighted_parts)


def _apply_keyword_highlight(text: str, keywords_input: str) -> str:
    if not text or not keywords_input:
        return escape_html(text)

    # 全角・半角スペース、読点、カンマ、中点で分割
    keywords = [
        k.strip() for k in re.split(r"[\s、，,・]+", keywords_input) if k.strip()
    ]

    if not keywords:
        return escape_html(text)

    # 文字列長の降順でソート
    keywords = sorted(list(set(keywords)), key=len, reverse=True)

    escaped_keywords = [re.escape(kw) for kw in keywords]
    pattern = r"(" + "|".join(escaped_keywords) + r")"

    highlighted_parts: list[str] = []
    last_end = 0
    for match in re.finditer(pattern, text):
        highlighted_parts.append(escape_html(text[last_end : match.start()]))
        highlighted_parts.append(_highlight_span(match.group(0)))
        last_end = match.end()

    highlighted_parts.append(escape_html(text[last_end:]))
    return "".join(highlighted_parts)


# ============ 旧API互換 ============


def parse_blanks_from_text(text: str) -> list[dict[str, Any]]:
    """【】マーカーからカードを生成（旧方式との互換性のため残す）"""
    is_valid, _message, _count = validate_blank_markers(text)
    if not is_valid:
        return []

    pattern = r"【([^【】]+)】"
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
    if not contains_highlight_markers(text):
        return False, "穴埋め箇所が指定されていません。", 0
    return _validate_markers(text, label="穴埋め")


def generate_flashcards(text: str) -> list[dict[str, Any]] | None:
    """旧API互換のエントリーポイント"""
    is_valid, _message, _count = validate_blank_markers(text)
    if not is_valid:
        return None
    return parse_blanks_from_text(text)


def count_card_blanks(question: str) -> int:
    """編集後の問題文に残る穴埋めプレースホルダー数を返す。"""
    return len(re.findall(r"_{3,}", question))


def apply_highlight(text: str, keywords_input: str) -> str:
    """知識・類型カード向けのハイライトHTMLを生成する。"""
    if contains_highlight_markers(text):
        is_valid, _message, _count = validate_highlight_markers(text)
        if is_valid:
            return _apply_marker_highlight(text)
        return escape_html(text)

    return _apply_keyword_highlight(text, keywords_input)
