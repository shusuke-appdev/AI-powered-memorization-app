"""
本日のノルマページ — 復習UI
"""

from __future__ import annotations

import datetime

import streamlit as st

from auth import get_daily_quota_limit
from services.card_service import apply_highlight
from services.review_service import calculate_next_review, select_hybrid_quota
from storage import (
    get_source_cards_by_ids,
    load_cards,
    toggle_favorite_by_source_id,
    update_card_progress,
)


def render_review_page(user_id: str, api_key: str) -> None:
    """本日のノルマタブを表示"""
    st.title("本日のノルマ")

    cards = load_cards(user_id)
    today = datetime.date.today().isoformat()
    daily_limit = get_daily_quota_limit(user_id)

    # 日付が変わったらセッションをリセット
    if st.session_state.get("quota_date") != today:
        st.session_state.quota_date = today
        st.session_state.reviewed_source_ids = []
        st.session_state.reviewed_card_ids = []
        st.session_state.reviewed_card_count = 0
        st.session_state.quota_card_ids = None

    reviewed_card_ids = set(st.session_state.get("reviewed_card_ids", []))

    # その日のノルマカードIDが未設定なら選択（初回 or ノルマ変更時）
    if st.session_state.get("quota_card_ids") is None:
        all_due_cards = [c for c in cards if c["next_review"] <= today]

        if reviewed_card_ids:
            # ノルマ変更: 既レビュー済みカードを保持し、不足分を追加選択
            remaining_slots = max(0, daily_limit - len(reviewed_card_ids))
            # 既レビュー済みを除いた候補から追加分を選択
            unreviewed_due = [
                c for c in all_due_cards if c["id"] not in reviewed_card_ids
            ]
            additional = select_hybrid_quota(unreviewed_due, remaining_slots, cards)
            new_quota_ids = list(reviewed_card_ids) + [
                c["id"] for c in additional
            ]
            st.session_state.quota_card_ids = new_quota_ids
        else:
            # 初回: 通常の選択
            selected_cards = select_hybrid_quota(all_due_cards, daily_limit, cards)
            st.session_state.quota_card_ids = [c["id"] for c in selected_cards]

    quota_card_ids = set(st.session_state.get("quota_card_ids", []))
    remaining_quota_ids = quota_card_ids - reviewed_card_ids

    cards_by_id = {c["id"]: c for c in cards}
    due_cards = [
        cards_by_id[cid] for cid in remaining_quota_ids if cid in cards_by_id
    ]
    due_cards.sort(key=lambda c: c.get("next_review", "9999-99-99"))

    all_due_cards = [c for c in cards if c["next_review"] <= today]

    if not due_cards:
        _render_completion(cards, all_due_cards, daily_limit, user_id)
    else:
        _render_study_card(due_cards, cards, user_id)


def _render_completion(
    cards: list[dict],
    all_due_cards: list[dict],
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
    reviewed_source_ids = st.session_state.get("reviewed_source_ids", [])
    if reviewed_source_ids:
        _render_source_review(reviewed_source_ids, cards, user_id)


def _render_source_review(
    reviewed_source_ids: list[str],
    cards: list[dict],
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
            st.session_state.reviewed_source_ids = []
            st.rerun()
        return

    if "source_review_index" not in st.session_state:
        st.session_state.source_review_index = 0

    if st.session_state.source_review_index >= len(source_cards):
        st.session_state.source_review_index = 0

    current_source = source_cards[st.session_state.source_review_index]

    st.progress(
        (st.session_state.source_review_index + 1) / len(source_cards),
        text=f"原文 {st.session_state.source_review_index + 1} / {len(source_cards)}",
    )

    category = current_source.get("category", "その他")
    title_html = (
        f'<div class="flashcard-title">{current_source.get("title", "")}</div>'
        if current_source.get("title")
        else ""
    )
    st.markdown(
        f"""
<div class="flashcard flashcard-bg-{category}">
    {title_html}
    <div class="flashcard-category category-{category}">{category}</div>
    <div class="flashcard-question" style="font-size: 18px; text-align: left;">{current_source.get("source_text", "")}</div>
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
            st.session_state.reviewed_source_ids = []
            st.session_state.source_review_index = 0
            st.rerun()

    with nav_col3:
        if st.session_state.source_review_index < len(source_cards) - 1:
            if st.button("次へ ▶", use_container_width=True):
                st.session_state.source_review_index += 1
                st.rerun()
        elif st.session_state.source_review_index > 0:
            if st.button("◀ 前へ", use_container_width=True):
                st.session_state.source_review_index -= 1
                st.rerun()


def _render_study_card(
    due_cards: list[dict],
    cards: list[dict],
    user_id: str,
) -> None:
    """学習カードの表示"""
    total_quota = len(st.session_state.get("quota_card_ids", []))
    quota_ids_set = set(st.session_state.get("quota_card_ids", []))
    reviewed_ids_set = set(st.session_state.get("reviewed_card_ids", []))
    reviewed_count = len(quota_ids_set & reviewed_ids_set)
    remaining = len(due_cards)
    progress = reviewed_count / total_quota if total_quota > 0 else 0
    st.progress(
        progress,
        text=f"本日の進捗: {reviewed_count} / {total_quota} 枚完了（残り {remaining} 枚）",
    )

    if "current_card_index" not in st.session_state:
        st.session_state.current_card_index = 0

    if st.session_state.current_card_index >= len(due_cards):
        st.session_state.current_card_index = 0

    current_card = due_cards[st.session_state.current_card_index]

    # カード表示
    is_fav = current_card.get("is_favorite", False)
    fav_star = "⭐" if is_fav else "☆"

    card_type = current_card.get("card_type")
    is_highlight_mode = card_type in ("知識", "類型")
    question_html = current_card["question"]

    if is_highlight_mode:
        hl_keys = current_card.get("highlighted_keywords", "")
        if hl_keys:
            question_html = apply_highlight(question_html, hl_keys)
        show_eval_buttons = True
    else:
        show_eval_buttons = st.session_state.get("show_answer", False)

    category = current_card.get("category", "その他")
    title_html = (
        f'<div class="flashcard-title">{current_card.get("title", "")}</div>'
        if current_card.get("title")
        else ""
    )
    answer_html = (
        f'<div class="flashcard-answer">{current_card["answer"]}</div>'
        if show_eval_buttons and not is_highlight_mode
        else ""
    )

    card_html = f"""
<div class="flashcard flashcard-bg-{category}">
    {title_html}
    <div class="flashcard-category category-{category}">
        {fav_star} {category}
    </div>
    <div class="flashcard-question">{question_html}</div>
    {answer_html}
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)

    # ボタン
    if not show_eval_buttons:
        if st.button("答えを見る", type="primary", use_container_width=True):
            st.session_state.show_answer = True
            st.rerun()
    else:
        st.markdown(
            "<div style='text-align: center; margin-bottom: 10px; color: #6b7280;'>どれくらい覚えていましたか？</div>",
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)

        def process_review(quality: int) -> None:
            card_id = current_card["id"]
            if "reviewed_card_ids" not in st.session_state:
                st.session_state.reviewed_card_ids = []
            if card_id not in st.session_state.reviewed_card_ids:
                st.session_state.reviewed_card_ids.append(card_id)
                st.session_state.reviewed_card_count = (
                    st.session_state.get("reviewed_card_count", 0) + 1
                )

            source_id = current_card.get("source_id")
            if source_id:
                if "reviewed_source_ids" not in st.session_state:
                    st.session_state.reviewed_source_ids = []
                if source_id not in st.session_state.reviewed_source_ids:
                    st.session_state.reviewed_source_ids.append(source_id)

            new_stats = calculate_next_review(quality, current_card)
            update_card_progress(user_id, current_card["id"], new_stats)
            st.session_state.show_answer = False
            st.rerun()

        with col1:
            if st.button("忘れた (0)", use_container_width=True):
                process_review(0)
        with col2:
            if st.button("難しい (3)", use_container_width=True):
                process_review(3)
        with col3:
            if st.button("普通 (4)", use_container_width=True):
                process_review(4)
        with col4:
            if st.button("簡単 (5)", type="primary", use_container_width=True):
                process_review(5)
