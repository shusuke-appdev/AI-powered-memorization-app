"""
本日のノルマページ — 復習UI
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from auth import get_daily_quota_limit
from services.card_service import apply_highlight
from services.html_rendering import escape_html, safe_category_class
from services.review_service import calculate_next_review, reconcile_daily_quota
from services.time_service import local_date_iso
from storage import (
    get_source_cards_by_ids,
    load_cards,
    load_daily_assignments,
    mark_daily_assignment_complete,
    save_daily_assignments,
    toggle_favorite_by_source_id,
    update_card_progress,
)

# セッション状態キー
_SK_QUOTA_DATE = "quota_date"
_SK_REVIEWED_SOURCE_IDS = "reviewed_source_ids"
_SK_REVIEWED_CARD_IDS = "reviewed_card_ids"
_SK_REVIEWED_CARD_COUNT = "reviewed_card_count"
_SK_QUOTA_CARD_IDS = "quota_card_ids"
_SK_CURRENT_CARD_INDEX = "current_card_index"
_SK_SHOW_ANSWER = "show_answer"
_SK_SOURCE_REVIEW_INDEX = "source_review_index"


def render_review_page(user_id: str) -> None:
    """本日のノルマタブを表示"""
    st.title("本日のノルマ")

    cards = load_cards(user_id)
    today = local_date_iso()
    daily_limit = get_daily_quota_limit(user_id)

    # 日付が変わったらセッションをリセット
    if st.session_state.get(_SK_QUOTA_DATE) != today:
        st.session_state[_SK_QUOTA_DATE] = today
        st.session_state[_SK_REVIEWED_SOURCE_IDS] = []
        st.session_state[_SK_REVIEWED_CARD_IDS] = []
        st.session_state[_SK_REVIEWED_CARD_COUNT] = 0
        st.session_state[_SK_QUOTA_CARD_IDS] = None

    # 期日カードの抽出（時刻付き文字列に対応するため先頭10文字だけで比較）
    all_due_cards = [c for c in cards if str(c.get("next_review", ""))[:10] <= today]
    cards_by_id: dict[str, dict[str, Any]] = {str(c["id"]): c for c in cards}

    assignments = load_daily_assignments(user_id, today)
    if assignments:
        quota_card_id_list = [
            str(item["card_id"])
            for item in assignments
            if str(item.get("card_id")) in cards_by_id
        ]
        db_reviewed_ids = [
            str(item["card_id"]) for item in assignments if item.get("completed_at")
        ]
        session_reviewed_ids: list[str] = st.session_state.get(
            _SK_REVIEWED_CARD_IDS, []
        )
        reviewed_card_id_list = list(
            dict.fromkeys(db_reviewed_ids + session_reviewed_ids)
        )
        reviewed_source_ids = [
            str(item["source_id"])
            for item in assignments
            if item.get("completed_at") and item.get("source_id")
        ]
        st.session_state[_SK_QUOTA_CARD_IDS] = quota_card_id_list
        st.session_state[_SK_REVIEWED_CARD_IDS] = reviewed_card_id_list
        if reviewed_source_ids:
            st.session_state[_SK_REVIEWED_SOURCE_IDS] = list(
                dict.fromkeys(reviewed_source_ids)
            )
    else:
        reviewed_card_id_list = st.session_state.get(_SK_REVIEWED_CARD_IDS, [])
        current_quota_ids = st.session_state.get(_SK_QUOTA_CARD_IDS)
        quota_card_id_list = reconcile_daily_quota(
            current_quota_ids,
            reviewed_card_id_list,
            all_due_cards,
            daily_limit,
            cards,
        )
        if quota_card_id_list != current_quota_ids:
            st.session_state[_SK_QUOTA_CARD_IDS] = quota_card_id_list
        save_daily_assignments(user_id, today, quota_card_id_list, cards_by_id)

    reviewed_card_ids: set[str] = set(reviewed_card_id_list)
    due_cards = [
        cards_by_id[cid]
        for cid in quota_card_id_list
        if cid not in reviewed_card_ids and cid in cards_by_id
    ]
    due_cards.sort(key=lambda c: str(c.get("next_review", "9999-99-99"))[:10])

    if not due_cards:
        _render_completion(cards, all_due_cards, daily_limit, user_id)
    else:
        _render_study_card(due_cards, cards, user_id)


def _render_completion(
    cards: list[dict[str, Any]],
    all_due_cards: list[dict[str, Any]],
    daily_limit: int,
    user_id: str,
) -> None:
    """ノルマ完了時の表示"""
    st.markdown(
        """
    <div style="text-align: center; padding: 50px;">
        <h2>🎉 本日のノルマ完了！</h2>
        <p style="color: #6b7280;">今日のノルマは終了しました。お疲れ様でした！</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.metric("デッキのカード総数", len(cards))
    if len(all_due_cards) > daily_limit:
        st.info(
            f"💡 残り {len(all_due_cards) - daily_limit} 枚のカードが復習待ちです（明日以降）"
        )

    # ノルマ復習モード（原文カードレビュー）
    reviewed_source_ids: list[str] = st.session_state.get(_SK_REVIEWED_SOURCE_IDS, [])
    if reviewed_source_ids:
        _render_source_review(reviewed_source_ids, cards, user_id)


def _render_source_review(
    reviewed_source_ids: list[str],
    cards: list[dict[str, Any]],
    user_id: str,
) -> None:
    """原文カード復習セクション"""
    st.markdown("---")
    st.subheader("📖 ノルマ復習（原文確認）")
    st.markdown("今日復習したカードの原文を確認できます。")

    source_cards = get_source_cards_by_ids(list(set(reviewed_source_ids)))

    if not source_cards:
        st.info("原文カードが見つかりませんでした。")
        if st.button("クリア"):
            st.session_state[_SK_REVIEWED_SOURCE_IDS] = []
            st.rerun()
        return

    if _SK_SOURCE_REVIEW_INDEX not in st.session_state:
        st.session_state[_SK_SOURCE_REVIEW_INDEX] = 0

    if st.session_state[_SK_SOURCE_REVIEW_INDEX] >= len(source_cards):
        st.session_state[_SK_SOURCE_REVIEW_INDEX] = 0

    current_source = source_cards[st.session_state[_SK_SOURCE_REVIEW_INDEX]]

    st.progress(
        (st.session_state[_SK_SOURCE_REVIEW_INDEX] + 1) / len(source_cards),
        text=f"原文 {st.session_state[_SK_SOURCE_REVIEW_INDEX] + 1} / {len(source_cards)}",
    )

    category_value = current_source.get("category", "その他")
    category = safe_category_class(category_value)
    category_label = escape_html(category_value)
    title_html = (
        f'<div class="flashcard-title">{escape_html(current_source.get("title", ""))}</div>'
        if current_source.get("title")
        else ""
    )
    source_text = escape_html(current_source.get("source_text", ""))
    st.markdown(
        f"""
<div class="flashcard flashcard-bg-{category}">
    {title_html}
    <div class="flashcard-category category-{category}">{category_label}</div>
    <div class="flashcard-question" style="font-size: 18px; text-align: left;">{source_text}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    related_cards = [c for c in cards if c.get("source_id") == current_source["id"]]
    is_source_fav = any(c.get("is_favorite", False) for c in related_cards)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])

    with nav_col1:
        fav_label = "⭐ 解除" if is_source_fav else "☆ 登録"
        if st.button(
            fav_label,
            key=f"source_fav_{current_source['id']}",
            use_container_width=True,
        ):
            toggle_favorite_by_source_id(
                user_id, current_source["id"], not is_source_fav
            )
            st.rerun()

    with nav_col2:
        if st.button("✓ 復習を終了", type="primary", use_container_width=True):
            st.session_state[_SK_REVIEWED_SOURCE_IDS] = []
            st.session_state[_SK_SOURCE_REVIEW_INDEX] = 0
            st.rerun()

    with nav_col3:
        if st.session_state[_SK_SOURCE_REVIEW_INDEX] < len(source_cards) - 1:
            if st.button("次へ ▶", use_container_width=True):
                st.session_state[_SK_SOURCE_REVIEW_INDEX] += 1
                st.rerun()
        elif st.session_state[_SK_SOURCE_REVIEW_INDEX] > 0:
            if st.button("◀ 前へ", use_container_width=True):
                st.session_state[_SK_SOURCE_REVIEW_INDEX] -= 1
                st.rerun()


def _render_study_card(
    due_cards: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    user_id: str,
) -> None:
    """学習カードの表示"""
    total_quota = len(st.session_state.get(_SK_QUOTA_CARD_IDS, []))
    quota_ids_set = set(st.session_state.get(_SK_QUOTA_CARD_IDS, []))
    reviewed_ids_set = set(st.session_state.get(_SK_REVIEWED_CARD_IDS, []))
    reviewed_count = len(quota_ids_set & reviewed_ids_set)
    remaining = len(due_cards)
    progress = reviewed_count / total_quota if total_quota > 0 else 0
    st.progress(
        progress,
        text=f"本日の進捗: {reviewed_count} / {total_quota} 枚完了（残り {remaining} 枚）",
    )

    if _SK_CURRENT_CARD_INDEX not in st.session_state:
        st.session_state[_SK_CURRENT_CARD_INDEX] = 0

    if st.session_state[_SK_CURRENT_CARD_INDEX] >= len(due_cards):
        st.session_state[_SK_CURRENT_CARD_INDEX] = 0

    current_card = due_cards[st.session_state[_SK_CURRENT_CARD_INDEX]]

    # カード表示
    is_fav = current_card.get("is_favorite", False)
    fav_star = "⭐" if is_fav else "☆"

    card_type = current_card.get("card_type")
    is_highlight_mode = card_type in ("知識", "類型")
    question_html = escape_html(current_card["question"])

    if is_highlight_mode:
        hl_keys = current_card.get("highlighted_keywords", "")
        question_html = apply_highlight(current_card["question"], hl_keys)
        show_eval_buttons = True
    else:
        show_eval_buttons = st.session_state.get(_SK_SHOW_ANSWER, False)

    category_value = current_card.get("category", "その他")
    category = safe_category_class(category_value)
    category_label = escape_html(category_value)
    title_html = (
        f'<div class="flashcard-title">{escape_html(current_card.get("title", ""))}</div>'
        if current_card.get("title")
        else ""
    )
    answer_html = (
        f'<div class="flashcard-answer">{escape_html(current_card["answer"])}</div>'
        if show_eval_buttons and not is_highlight_mode
        else ""
    )

    card_html = f"""
<div class="flashcard flashcard-bg-{category}">
    {title_html}
    <div class="flashcard-category category-{category}">
        {fav_star} {category_label}
    </div>
    <div class="flashcard-question">{question_html}</div>
    {answer_html}
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)

    # ボタン
    if not show_eval_buttons:
        if st.button("答えを見る", type="primary", use_container_width=True):
            st.session_state[_SK_SHOW_ANSWER] = True
            st.rerun()
    else:
        st.markdown(
            "<div style='text-align: center; margin-bottom: 10px; color: #6b7280;'>どれくらい覚えていましたか？</div>",
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("忘れた (0)", use_container_width=True):
                _process_review(user_id, current_card, quality=0)
        with col2:
            if st.button("難しい (3)", use_container_width=True):
                _process_review(user_id, current_card, quality=3)
        with col3:
            if st.button("普通 (4)", use_container_width=True):
                _process_review(user_id, current_card, quality=4)
        with col4:
            if st.button("簡単 (5)", type="primary", use_container_width=True):
                _process_review(user_id, current_card, quality=5)


def _process_review(user_id: str, card: dict[str, Any], *, quality: int) -> None:
    """レビュー結果を処理しセッション状態を更新"""
    card_id: str = card["id"]
    if _SK_REVIEWED_CARD_IDS not in st.session_state:
        st.session_state[_SK_REVIEWED_CARD_IDS] = []
    if card_id not in st.session_state[_SK_REVIEWED_CARD_IDS]:
        st.session_state[_SK_REVIEWED_CARD_IDS].append(card_id)
        st.session_state[_SK_REVIEWED_CARD_COUNT] = (
            st.session_state.get(_SK_REVIEWED_CARD_COUNT, 0) + 1
        )

    source_id = card.get("source_id")
    if source_id:
        if _SK_REVIEWED_SOURCE_IDS not in st.session_state:
            st.session_state[_SK_REVIEWED_SOURCE_IDS] = []
        if source_id not in st.session_state[_SK_REVIEWED_SOURCE_IDS]:
            st.session_state[_SK_REVIEWED_SOURCE_IDS].append(source_id)

    new_stats = calculate_next_review(quality, card)
    update_card_progress(user_id, card["id"], new_stats)
    mark_daily_assignment_complete(
        user_id,
        local_date_iso(),
        card["id"],
        quality=quality,
    )
    st.session_state[_SK_SHOW_ANSWER] = False
    st.rerun()
