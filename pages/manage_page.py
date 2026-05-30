"""
カード管理ページ — カード一覧・編集・削除UI
"""

from __future__ import annotations

import streamlit as st

from config import CARD_TYPES, CATEGORIES, RANKS
from services.card_service import (
    contains_highlight_markers,
    extract_highlight_keywords,
    parse_blanks_from_text,
    validate_highlight_markers,
)
from storage import (
    delete_card,
    delete_cards_batch,
    delete_source_card,
    load_cards,
    load_source_cards,
    toggle_favorite_by_source_id,
    update_card_content,
    update_source_card,
)
from use_cases.card_workflows import replace_source_cards


def render_manage_page(user_id: str) -> None:
    """カード管理タブを表示"""
    st.title("🗂️ カード管理")

    cards = load_cards(user_id)
    source_cards = load_source_cards(user_id)

    if not source_cards and not cards:
        st.info(
            "まだカードがありません。「カードを追加」メニューから作成してください。"
        )
        return

    st.markdown(f"**原文カード: {len(source_cards)} 件 / 暗記カード: {len(cards)} 枚**")

    # フィルタ
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        search_query = st.text_input(
            "🔍 検索",
            placeholder="タイトル、原文、問題、答えで検索...",
            key="unified_search",
        )
    with filter_col2:
        types_filter = ["すべて"] + CARD_TYPES
        selected_type_filter = st.selectbox(
            "タイプ絞り込み", types_filter, key="manage_type_filter"
        )

    # カテゴリタブ
    tabs = st.tabs(CATEGORIES)

    for i, category in enumerate(CATEGORIES):
        with tabs[i]:
            _render_category_tab(
                user_id,
                category,
                cards,
                source_cards,
                search_query,
                selected_type_filter,
            )


def _render_category_tab(
    user_id: str,
    category: str,
    cards: list[dict],
    source_cards: list[dict],
    search_query: str,
    selected_type_filter: str,
) -> None:
    """カテゴリタブの内容を表示"""
    category_sources = [
        s for s in source_cards if s.get("category", "その他") == category
    ]

    if selected_type_filter != "すべて":
        category_sources = [
            s for s in category_sources if s.get("card_type") == selected_type_filter
        ]

    if search_query:
        query_lower = search_query.lower()
        category_sources = [
            s
            for s in category_sources
            if query_lower in s.get("source_text", "").lower()
            or query_lower in s.get("title", "").lower()
        ]

    orphan_cards = [
        c
        for c in cards
        if c.get("category", "その他") == category and not c.get("source_id")
    ]
    if search_query:
        query_lower = search_query.lower()
        orphan_cards = [
            c
            for c in orphan_cards
            if query_lower in c["question"].lower()
            or query_lower in c["answer"].lower()
            or query_lower in c.get("title", "").lower()
        ]

    if not category_sources and not orphan_cards:
        st.info(f"{category} のカードはありません。")
        return

    for sc in category_sources:
        _render_source_card_expander(user_id, sc, cards, category)

    if orphan_cards:
        st.markdown("---")
        st.markdown("**📎 原文なしの暗記カード**")
        for card in orphan_cards:
            _render_orphan_card(user_id, card)


def _render_source_card_expander(
    user_id: str,
    sc: dict,
    cards: list[dict],
    category: str,
) -> None:
    """原文カードのExpanderを表示"""
    source_id = sc["id"]
    source_title = sc.get("title", "")
    display_title = source_title or "無題"
    source_text = sc.get("source_text", "")

    linked_cards = [c for c in cards if c.get("source_id") == source_id]

    with st.expander(
        f"📄 {display_title}（暗記カード {len(linked_cards)} 枚）", expanded=False
    ):
        edited_title = st.text_input(
            "タイトル", value=source_title, key=f"edit_title_{source_id}"
        )

        # 原文表示・編集
        st.markdown("**📝 原文**")
        edited_source = st.text_area(
            "", value=source_text, height=120, key=f"edit_source_{source_id}"
        )

        meta_col1, meta_col2 = st.columns(2)
        with meta_col1:
            current_type = sc.get("card_type")
            type_index = (
                CARD_TYPES.index(current_type) if current_type in CARD_TYPES else 0
            )
            new_type = st.selectbox(
                "タイプ", CARD_TYPES, index=type_index, key=f"edit_type_{source_id}"
            )
        with meta_col2:
            cat_index = CATEGORIES.index(category) if category in CATEGORIES else 0
            new_category = st.selectbox(
                "カテゴリ", CATEGORIES, index=cat_index, key=f"edit_cat_{source_id}"
            )

        title_modified = edited_title != source_title
        source_modified = edited_source != source_text
        type_modified = new_type != sc.get("card_type")
        cat_modified = new_category != category

        # 紐づき暗記カード
        if linked_cards:
            st.markdown("---")
            st.markdown("**🎴 紐づき暗記カード**")
            for j, card in enumerate(linked_cards):
                _render_linked_card_row(user_id, card, j, sc)

        # 変更の検知
        any_card_modified = False
        changed_items = []
        if title_modified:
            changed_items.append("タイトル")
        if source_modified:
            changed_items.append("原文")
        if type_modified:
            changed_items.append("タイプ")
        if cat_modified:
            changed_items.append("カテゴリ")

        for j, card in enumerate(linked_cards):
            c_type = (
                new_type
                if type_modified
                else card.get("card_type", sc.get("card_type"))
            )
            new_q = st.session_state.get(f"q_{card['id']}")
            if new_q is not None and new_q != card["question"]:
                any_card_modified = True
                changed_items.append(f"カード{j + 1}の問題")

            if c_type in ("知識", "類型"):
                new_highlights = _highlight_keywords_for_save(
                    new_q or card["question"],
                    card["question"],
                    card.get("highlighted_keywords", ""),
                )
                if new_highlights != card.get("highlighted_keywords", ""):
                    any_card_modified = True
                    changed_items.append(f"カード{j + 1}のハイライト指定")
            else:
                new_a = st.session_state.get(f"a_{card['id']}")
                if new_a is not None and new_a != card["answer"]:
                    any_card_modified = True
                    changed_items.append(f"カード{j + 1}の答え")

            new_r = st.session_state.get(f"r_{card['id']}")
            if new_r is not None and new_r != card.get("rank", "B"):
                any_card_modified = True
                changed_items.append(f"カード{j + 1}のランク")

        has_changes = (
            title_modified
            or source_modified
            or type_modified
            or cat_modified
            or any_card_modified
        )

        # 操作ボタン
        st.markdown("---")
        is_source_fav = any(c.get("is_favorite", False) for c in linked_cards)
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])

        with btn_col1:
            if st.button(
                "💾 保存",
                key=f"save_source_{source_id}",
                type="primary",
                use_container_width=True,
                disabled=not has_changes,
            ):
                _save_source_and_cards(
                    user_id,
                    source_id,
                    sc,
                    linked_cards,
                    edited_title,
                    edited_source,
                    new_type,
                    new_category,
                    title_modified,
                    source_modified,
                    type_modified,
                    cat_modified,
                    changed_items,
                )

        with btn_col2:
            fav_label = "⭐ 解除" if is_source_fav else "☆ 登録"
            if st.button(
                fav_label, key=f"edit_fav_{source_id}", use_container_width=True
            ):
                toggle_favorite_by_source_id(user_id, source_id, not is_source_fav)
                st.rerun()

        with btn_col3:
            if st.button(
                "🗑️ 全削除", key=f"del_all_{source_id}", use_container_width=True
            ):
                st.session_state[f"confirm_del_all_{source_id}"] = True

        # 削除確認
        if st.session_state.get(f"confirm_del_all_{source_id}", False):
            st.warning("⚠️ この原文カードと紐づく暗記カードを全て削除しますか？")
            c1, c2, c3 = st.columns([1, 1, 3])
            with c1:
                if st.button("✓ 削除", key=f"yes_del_all_{source_id}", type="primary"):
                    # N+1 → バッチ削除に最適化
                    card_ids = [card["id"] for card in linked_cards]
                    if card_ids:
                        delete_cards_batch(user_id, card_ids)
                    delete_source_card(user_id, source_id)
                    del st.session_state[f"confirm_del_all_{source_id}"]
                    st.success("削除しました")
                    st.rerun()
            with c2:
                if st.button("✗ 戻る", key=f"no_del_all_{source_id}"):
                    del st.session_state[f"confirm_del_all_{source_id}"]
                    st.rerun()

        # 変更した原文からカードを再生成
        if new_type not in ("知識", "類型"):
            st.markdown("---")
            if st.button("✨ 変更した原文からカードを再生成", key=f"regen_{source_id}"):
                new_cards = parse_blanks_from_text(edited_source)
                if new_cards:
                    st.session_state[f"regen_cards_{source_id}"] = new_cards
                else:
                    st.error("【】で穴埋め箇所を正しく指定してください。")

        regen_cards = st.session_state.get(f"regen_cards_{source_id}")
        if regen_cards:
            st.markdown("### 🔄 再生成プレビュー")
            st.warning(
                "「この内容で上書き保存」を押すと、既存の紐づきカードは削除され、以下のカードで上書きされます。"
            )
            cards_to_save = []
            for i, c in enumerate(regen_cards):
                c1, c2 = st.columns(2)
                with c1:
                    q = st.text_input(
                        f"新問題 {i + 1}",
                        value=c["question"],
                        key=f"regen_q_{source_id}_{i}",
                    )
                with c2:
                    a = st.text_input(
                        f"新答え {i + 1}",
                        value=c["answer"],
                        key=f"regen_a_{source_id}_{i}",
                    )
                cards_to_save.append({"question": q, "answer": a})

            if st.button(
                "💾 この内容で暗記カードを上書き保存",
                type="primary",
                key=f"save_regen_{source_id}",
            ):
                cards_payload = [
                    {
                        "question": c["question"],
                        "answer": c["answer"],
                        "title": edited_title,
                        "category": new_category,
                        "blank_count": len(cards_to_save),
                        "card_type": new_type,
                        "rank": "B",
                    }
                    for c in cards_to_save
                    if c["question"] and c["answer"]
                ]
                replace_source_cards(
                    user_id,
                    source_id=source_id,
                    source_text=edited_source,
                    title=edited_title,
                    category=new_category,
                    card_type=new_type,
                    old_card_ids=[lc["id"] for lc in linked_cards],
                    cards=cards_payload,
                )
                del st.session_state[f"regen_cards_{source_id}"]
                st.success("再生成したカードで上書き保存しました！")
                st.rerun()
            if st.button("キャンセル", key=f"cancel_regen_{source_id}"):
                del st.session_state[f"regen_cards_{source_id}"]
                st.rerun()


def _render_linked_card_row(user_id: str, card: dict, index: int, sc: dict) -> None:
    """紐づきカードの1行を表示"""
    current_card_type = card.get("card_type", sc.get("card_type"))
    if current_card_type in ("知識", "類型"):
        col1, col3, col4 = st.columns([8, 2, 1])
        with col1:
            st.text_area(
                f"本文 {index + 1}（ハイライト箇所は【】で囲む）",
                value=card["question"],
                key=f"q_{card['id']}",
            )
    else:
        col1, col2, col3, col4 = st.columns([4, 4, 2, 1])
        with col1:
            st.text_area(
                f"問題 {index + 1}", value=card["question"], key=f"q_{card['id']}"
            )
        with col2:
            st.text_area(
                f"答え {index + 1}", value=card["answer"], key=f"a_{card['id']}"
            )

    with col3:
        current_rank = card.get("rank", "B")
        r_idx = RANKS.index(current_rank) if current_rank in RANKS else 3
        st.selectbox(f"ランク {index + 1}", RANKS, index=r_idx, key=f"r_{card['id']}")
    with col4:
        st.markdown("")
        if st.button("🗑️", key=f"del_single_{card['id']}", help="このカードのみ削除"):
            delete_card(user_id, card["id"])
            st.success("カードを削除しました")
            st.rerun()


def _highlight_keywords_for_save(
    new_text: str, previous_text: str, previous_keywords: str
) -> str:
    """旧方式カードは本文に【】がない限り既存ハイライト語を保持する。"""
    if contains_highlight_markers(new_text):
        return extract_highlight_keywords(new_text)
    if contains_highlight_markers(previous_text):
        return ""
    return previous_keywords


def _save_source_and_cards(
    user_id: str,
    source_id: str,
    sc: dict,
    linked_cards: list[dict],
    new_title: str,
    edited_source: str,
    new_type: str,
    new_category: str,
    title_modified: bool,
    source_modified: bool,
    type_modified: bool,
    cat_modified: bool,
    changed_items: list[str],
) -> None:
    """原文カードと紐づき暗記カードを保存"""
    if new_type in ("知識", "類型"):
        source_is_valid, source_message, _count = validate_highlight_markers(
            edited_source
        )
        if not source_is_valid:
            st.warning(f"原文: {source_message}")
            return

    if title_modified or source_modified or type_modified or cat_modified:
        update_source_card(
            user_id,
            source_id,
            source_text=edited_source if source_modified else None,
            title=new_title if title_modified else None,
            category=new_category if cat_modified else None,
            card_type=new_type if type_modified else None,
        )

    updated_count = 0
    for card in linked_cards:
        new_q = st.session_state.get(f"q_{card['id']}", card["question"])
        c_type = (
            new_type if type_modified else card.get("card_type", sc.get("card_type"))
        )

        new_r = st.session_state.get(f"r_{card['id']}", card.get("rank", "B"))

        if c_type in ("知識", "類型"):
            card_is_valid, card_message, _count = validate_highlight_markers(new_q)
            if not card_is_valid:
                st.warning(f"{card.get('title', 'カード')}: {card_message}")
                return
            ans_to_save = ""
            hl_to_save = _highlight_keywords_for_save(
                new_q,
                card["question"],
                card.get("highlighted_keywords", ""),
            )
        else:
            new_a = st.session_state.get(f"a_{card['id']}", card["answer"])
            ans_to_save = new_a
            hl_to_save = card.get("highlighted_keywords", "")

        if (
            new_q != card["question"]
            or ans_to_save != card["answer"]
            or hl_to_save != card.get("highlighted_keywords", "")
            or new_r != card.get("rank", "B")
            or title_modified
            or type_modified
            or cat_modified
        ):
            update_card_content(
                user_id,
                card["id"],
                new_q,
                ans_to_save,
                new_title,
                new_category,
                new_type,
                rank=new_r,
                highlighted_keywords=hl_to_save,
            )
            updated_count += 1

    if changed_items:
        st.success(f"✅ 以下の項目を更新しました: {', '.join(changed_items)}")
    else:
        st.info("変更はありませんでした")
    st.rerun()


def _render_orphan_card(user_id: str, card: dict) -> None:
    """原文なしの孤立カードを表示"""
    card_title = card.get("title", "")
    display_title = card_title or "無題"
    with st.expander(f"🎴 {display_title}: {card['question'][:30]}..."):
        with st.form(key=f"orphan_form_{card['id']}"):
            new_title = st.text_input(
                "タイトル", value=card_title, key=f"orphan_title_{card['id']}"
            )
            current_type_orphan = card.get("card_type")
            q_label = (
                "本文（ハイライト箇所は【】で囲む）"
                if current_type_orphan in ("知識", "類型")
                else "問題"
            )
            new_q = st.text_area(q_label, value=card["question"])

            col_cat, col_type = st.columns(2)
            with col_cat:
                new_cat = st.selectbox(
                    "カテゴリ",
                    CATEGORIES,
                    index=CATEGORIES.index(card.get("category", "その他")),
                )
            with col_type:
                type_idx = (
                    CARD_TYPES.index(current_type_orphan)
                    if current_type_orphan in CARD_TYPES
                    else 0
                )
                new_type_orphan = st.selectbox(
                    "タイプ",
                    CARD_TYPES,
                    index=type_idx,
                    key=f"orphan_type_{card['id']}",
                )

            if new_type_orphan in ("知識", "類型"):
                st.caption("ハイライトしたい箇所を本文中の【】で囲んでください。")
                new_a = ""
            else:
                new_a = st.text_input("答え", value=card["answer"])

            if st.form_submit_button("✓ 更新"):
                highlighted_keywords = None
                if new_type_orphan in ("知識", "類型"):
                    is_valid, message, _count = validate_highlight_markers(new_q)
                    if not is_valid:
                        st.warning(message)
                        return
                    highlighted_keywords = _highlight_keywords_for_save(
                        new_q,
                        card["question"],
                        card.get("highlighted_keywords", ""),
                    )
                update_card_content(
                    user_id,
                    card["id"],
                    new_q,
                    new_a,
                    new_title,
                    new_cat,
                    card_type=new_type_orphan,
                    highlighted_keywords=highlighted_keywords,
                )
                st.success("更新しました")
                st.rerun()

        if st.button("🗑️ 削除", key=f"del_orphan_{card['id']}"):
            delete_card(user_id, card["id"])
            st.success("削除しました")
            st.rerun()
