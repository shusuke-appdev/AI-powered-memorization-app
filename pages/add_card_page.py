"""
カード追加ページ — 新規カード作成UI
"""

from __future__ import annotations

import re

import streamlit as st

from config import BLANK_DISABLED_TYPES, CARD_TYPES, CATEGORIES, RANKS
from services.ai_service import QuotaExceededError, split_into_phrases, suggest_blanks
from services.card_service import (
    apply_highlight,
    generate_cards_from_selection,
    parse_blanks_from_text,
)
from storage import add_card, add_source_card


def render_add_card_page(user_id: str, api_key: str) -> None:
    """カード追加タブを表示"""
    # セッション状態の初期化
    _init_session_state()

    # タイトルとクリアボタン
    title_col, cancel_col = st.columns([3, 1])
    with title_col:
        st.title("📝 新しいカードを追加")
    with cancel_col:
        st.markdown("")
        has_progress = (
            "phrases" in st.session_state
            or "generated_cards" in st.session_state
            or st.session_state.add_card_text
        )
        if has_progress:
            if st.button("🔄 クリア", type="secondary", use_container_width=True):
                _clear_all_state()
                st.rerun()

    # メタデータ入力
    selected_category = _render_category_select()
    selected_rank = _render_rank_select()
    selected_type = _render_type_select()
    card_title = _render_title_input()

    is_blank_disabled = selected_type in BLANK_DISABLED_TYPES

    if is_blank_disabled:
        _render_no_blank_flow(user_id, card_title, selected_category, selected_type, selected_rank)
    else:
        _render_blank_flow(
            user_id, api_key, card_title, selected_category, selected_type, selected_rank
        )


def _init_session_state() -> None:
    """入力フィールドのセッションステート初期化"""
    defaults = {
        "add_card_category": "",
        "add_card_title": "",
        "add_card_text": "",
        "add_card_type": "",
        "add_card_rank": "B",
        "add_card_highlight": "",
        "widget_key_counter": 0,
        "manual_mode": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _clear_all_state() -> None:
    """全ての関連セッション状態をクリア"""
    for key in ["phrases", "selected_indices", "generated_cards", "prev_manual_text"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.add_card_category = ""
    st.session_state.add_card_title = ""
    st.session_state.add_card_text = ""
    st.session_state.add_card_type = ""
    st.session_state.add_card_highlight = ""
    st.session_state.add_card_rank = "B"
    st.session_state.widget_key_counter += 1


def _render_category_select() -> str:
    """カテゴリ選択"""
    categories_with_placeholder = ["-- カテゴリを選択 --"] + CATEGORIES
    current_idx = 0
    if (
        st.session_state.add_card_category
        and st.session_state.add_card_category in CATEGORIES
    ):
        current_idx = categories_with_placeholder.index(
            st.session_state.add_card_category
        )
    selected_raw = st.selectbox(
        "カテゴリ",
        categories_with_placeholder,
        index=current_idx,
        key=f"category_select_{st.session_state.widget_key_counter}",
    )
    selected = selected_raw if selected_raw != "-- カテゴリを選択 --" else ""
    st.session_state.add_card_category = selected
    return selected


def _render_rank_select() -> str:
    """ランク選択"""
    rank_idx = RANKS.index(st.session_state.add_card_rank) if st.session_state.add_card_rank in RANKS else 3
    selected = st.selectbox(
        "重要度ランク",
        RANKS,
        index=rank_idx,
        key=f"rank_select_{st.session_state.widget_key_counter}",
        help="ランクが高いものほど優先的にノルマに出題されます。",
    )
    st.session_state.add_card_rank = selected
    return selected


def _render_type_select() -> str:
    """タイプ選択"""
    types_with_placeholder = ["-- タイプを選択 --"] + CARD_TYPES
    type_idx = 0
    if (
        st.session_state.add_card_type
        and st.session_state.add_card_type in CARD_TYPES
    ):
        type_idx = types_with_placeholder.index(st.session_state.add_card_type)
    selected_raw = st.selectbox(
        "タイプ",
        types_with_placeholder,
        index=type_idx,
        key=f"type_select_{st.session_state.widget_key_counter}",
        help="規範/判例: 穴埋めあり、類型/知識: 穴埋めなし",
    )
    selected = selected_raw if selected_raw != "-- タイプを選択 --" else ""
    st.session_state.add_card_type = selected
    return selected


def _render_title_input() -> str:
    """タイトル入力"""
    card_title = st.text_input(
        "カードのタイトル（共通）",
        value=st.session_state.add_card_title,
        placeholder="例: 不法行為, 契約総論",
        key=f"title_input_{st.session_state.widget_key_counter}",
        autocomplete="off",
    )
    st.session_state.add_card_title = card_title
    return card_title


def _render_no_blank_flow(
    user_id: str,
    card_title: str,
    selected_category: str,
    selected_type: str,
    selected_rank: str,
) -> None:
    """穴埋めなしタイプ（知識・類型）のフロー"""
    st.subheader("① テキストとハイライト語句を入力")
    st.info(
        f'📝 「{selected_type}」タイプ: 穴埋めなしで保存します。問題文中の特定の語句をハイライトしたい場合は以下で指定してください。'
    )

    source_text = st.text_area(
        "原文テキスト",
        value=st.session_state.add_card_text,
        height=200,
        placeholder="例: 民法第709条は不法行為による損害賠償を規定している。",
        key=f"text_input_{st.session_state.widget_key_counter}",
    )
    st.session_state.add_card_text = source_text

    highlight_text = st.text_input(
        "答え（ハイライトする語句）",
        value=st.session_state.add_card_highlight,
        placeholder="例: 不法行為 損害賠償",
        help="複数の語句をハイライトする場合は、スペースで区切って入力してください。",
        key=f"highlight_input_{st.session_state.widget_key_counter}",
    )
    st.session_state.add_card_highlight = highlight_text

    if source_text and highlight_text:
        preview_q = apply_highlight(source_text, highlight_text)
        st.markdown(
            f"<div style='font-size: 0.9em; padding: 12px; margin-bottom: 20px; background-color: #f9fafb; border-radius: 4px; border-left: 4px solid #3b82f6;'><strong>ハイライト表示プレビュー:</strong> <br/> {preview_q}</div>",
            unsafe_allow_html=True,
        )

    if st.button("💾 保存", type="primary", key="save_no_blank_btn"):
        if not source_text:
            st.warning("テキストを入力してください。")
        else:
            source_id = add_source_card(
                user_id, source_text, title=card_title,
                category=selected_category, card_type=selected_type,
            )
            add_card(
                user_id, source_text, "",
                title=card_title, category=selected_category,
                source_id=source_id, blank_count=0,
                card_type=selected_type, rank=selected_rank,
                highlighted_keywords=highlight_text,
            )
            st.success("保存しました！")
            _clear_all_state()
            st.rerun()


def _render_blank_flow(
    user_id: str,
    api_key: str,
    card_title: str,
    selected_category: str,
    selected_type: str,
    selected_rank: str,
) -> None:
    """穴埋めありタイプ（規範/判例/未選択）のフロー"""
    st.subheader("① テキストを入力")

    manual_mode = st.checkbox(
        "✍️ 手動で穴埋め箇所を指定する（【】で囲む）",
        value=st.session_state.manual_mode,
        key="manual_mode_checkbox",
    )
    st.session_state.manual_mode = manual_mode

    if manual_mode:
        st.info("💡 穴埋めにしたい箇所を【】で囲んでください。例: 民法【709条】は...")

    source_text = st.text_area(
        "",
        value=st.session_state.add_card_text,
        height=200,
        placeholder="例: 民法第709条は不法行為による損害賠償を規定している。\n\n手動モード時: 民法【709条】は【不法行為】による【損害賠償】を規定している。",
        key=f"text_input_{st.session_state.widget_key_counter}",
        label_visibility="collapsed",
    )
    st.session_state.add_card_text = source_text

    # 手動モードでテキストが変更されたら生成済みカードをクリア
    if manual_mode and "generated_cards" in st.session_state:
        prev_text = st.session_state.get("prev_manual_text", "")
        if source_text != prev_text:
            del st.session_state.generated_cards
            st.info("テキストが変更されました。再度「カード生成」を押してください。")
    if manual_mode:
        st.session_state.prev_manual_text = source_text

    if manual_mode:
        _render_manual_generate(source_text)
    else:
        _render_ai_analyze(source_text, api_key)

    # ステップ2: 穴埋め箇所を選択
    if "phrases" in st.session_state and st.session_state.phrases:
        _render_phrase_selection(api_key)

    # プレビュー＆保存
    if "generated_cards" in st.session_state:
        _render_save_form(
            user_id, card_title, selected_category, selected_type, selected_rank
        )


def _render_manual_generate(source_text: str) -> None:
    """手動モードのカード生成"""
    if st.button("✨ カード生成", type="primary", key="manual_generate_btn"):
        if not source_text:
            st.warning("テキストを入力してください。")
        elif "【" not in source_text or "】" not in source_text:
            st.warning("【】で穴埋め箇所を指定してください。例: 民法【709条】は...")
        else:
            cards = parse_blanks_from_text(source_text)
            if cards:
                st.session_state.generated_cards = cards
                st.success(f"{len(cards)} 枚のカードを生成しました！")
            else:
                st.error("カードの生成に失敗しました。【】で穴埋め箇所を正しく指定してください。")


def _render_ai_analyze(source_text: str, api_key: str) -> None:
    """AIモードのテキスト解析"""
    if st.button("📝 テキストを解析", type="primary"):
        if not source_text:
            st.warning("テキストを入力してください。")
        elif not api_key:
            st.warning("APIキーを設定してください。")
        else:
            with st.spinner("AIがテキストを解析中..."):
                try:
                    phrases = split_into_phrases(source_text, api_key)
                    if isinstance(phrases, dict) and phrases.get("error") == "API_QUOTA_EXCEEDED":
                        st.error(f"⚠️ {phrases.get('message', 'APIの利用制限に達しました。')}")
                    elif phrases:
                        st.session_state.phrases = phrases
                        st.session_state.selected_indices = []
                        st.success(f"{len(phrases)}個の文節に分割しました。穴埋め箇所を選択してください。")
                    else:
                        st.error("テキストの解析に失敗しました。")
                except QuotaExceededError as e:
                    st.error(f"⚠️ {e}")


def _render_phrase_selection(api_key: str) -> None:
    """穴埋め箇所の選択UI"""
    st.subheader("② 穴埋め箇所を選択")
    st.markdown("チェックを入れた箇所が穴埋め（______）になります。")

    phrases = st.session_state.phrases
    punctuation_pattern = r"^[。、，．,.！？!?：:；;\s①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]+$"

    if "selected_indices" not in st.session_state:
        st.session_state.selected_indices = []

    # AI提案ボタン
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🤖 AIに提案させる"):
            if api_key:
                with st.spinner("AIが提案中..."):
                    try:
                        suggested = suggest_blanks(phrases, api_key)
                        if isinstance(suggested, dict) and suggested.get("error") == "API_QUOTA_EXCEEDED":
                            st.error(f"⚠️ {suggested.get('message', 'APIの利用制限に達しました。')}")
                        else:
                            st.session_state.selected_indices = suggested
                            st.rerun()
                    except QuotaExceededError as e:
                        st.error(f"⚠️ {e}")
            else:
                st.warning("APIキーを設定してください。")

    # HTMLプレビュー
    phrase_buttons_html = []
    for i, phrase in enumerate(phrases):
        is_punctuation = re.match(punctuation_pattern, phrase)
        is_selected = i in st.session_state.selected_indices
        if is_punctuation:
            phrase_buttons_html.append(f"<span class='phrase-toggle punct'>{phrase}</span>")
        elif is_selected:
            phrase_buttons_html.append(f"<span class='phrase-toggle selected' data-idx='{i}'>{phrase}</span>")
        else:
            phrase_buttons_html.append(f"<span class='phrase-toggle normal' data-idx='{i}'>{phrase}</span>")

    st.markdown(f"<div class='phrase-grid'>{''.join(phrase_buttons_html)}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Streamlit ボタンでトグル
    selectable_phrases = [
        (i, phrase)
        for i, phrase in enumerate(phrases)
        if not re.match(punctuation_pattern, phrase)
    ]

    if selectable_phrases:
        rows = [selectable_phrases[i : i + 4] for i in range(0, len(selectable_phrases), 4)]
        for row in rows:
            cols = st.columns(len(row))
            for col_idx, (phrase_idx, phrase_text) in enumerate(row):
                with cols[col_idx]:
                    is_selected = phrase_idx in st.session_state.selected_indices
                    btn_label = f"✓ {phrase_text}" if is_selected else phrase_text
                    btn_type = "primary" if is_selected else "secondary"
                    if st.button(btn_label, key=f"toggle_{phrase_idx}", type=btn_type, use_container_width=True):
                        if phrase_idx in st.session_state.selected_indices:
                            st.session_state.selected_indices.remove(phrase_idx)
                        else:
                            st.session_state.selected_indices.append(phrase_idx)
                        st.rerun()

    # プレビュー
    selected = st.session_state.selected_indices.copy()
    if selected:
        preview_parts = []
        answer_groups = []
        current_answer_group: list[str] = []

        for i, phrase in enumerate(phrases):
            if i in selected:
                if not current_answer_group:
                    preview_parts.append("______")
                current_answer_group.append(phrase)
            else:
                if current_answer_group:
                    answer_groups.append("".join(current_answer_group))
                    current_answer_group = []
                preview_parts.append(phrase)

        if current_answer_group:
            answer_groups.append("".join(current_answer_group))

        st.markdown("**プレビュー:**")
        st.info("".join(preview_parts))
        st.markdown(f"**穴埋め箇所: {len(answer_groups)}個** (隣接ブロックは自動結合)")
        for idx, ans in enumerate(answer_groups, 1):
            st.markdown(f"  {idx}. {ans}")

    # カード生成ボタン
    if st.button("✨ カード生成", type="primary", key="generate_cards_btn"):
        if not selected:
            st.warning("穴埋め箇所を1つ以上選択してください。")
        else:
            cards = generate_cards_from_selection(phrases, selected)
            if cards:
                st.session_state.generated_cards = cards
                st.success(f"{len(cards)} 枚のカードを生成しました！")
            else:
                st.error("カードの生成に失敗しました。")


def _render_save_form(
    user_id: str,
    card_title: str,
    selected_category: str,
    selected_type: str,
    selected_rank: str,
) -> None:
    """生成カードのプレビューと保存フォーム"""
    st.subheader("プレビュー & 保存")

    with st.form("save_cards_form"):
        cards_to_save = []
        for i, card in enumerate(st.session_state.generated_cards):
            st.markdown(f"**カード {i + 1}**")
            col1, col2 = st.columns(2)
            with col1:
                q = st.text_input("問題", value=card["question"], key=f"q_{i}", label_visibility="collapsed", placeholder="問題")
            with col2:
                a_label = "答え（ハイライトする語句）" if selected_type in ("知識", "類型") else "答え"
                a = st.text_input(a_label, value=card["answer"], key=f"a_{i}", label_visibility="collapsed", placeholder="答え")
            cards_to_save.append({"question": q, "answer": a})

            if selected_type in ("知識", "類型") and a:
                preview_q = apply_highlight(q, a)
                st.markdown(
                    f"<div style='font-size: 0.9em; padding: 8px; background-color: #f9fafb; border-radius: 4px; border-left: 4px solid #3b82f6;'><strong>表示プレビュー:</strong> <br/> {preview_q}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("---")

        if st.form_submit_button("💾 デッキに保存", type="primary"):
            original_text = st.session_state.get("add_card_text", "")
            source_id = None
            if original_text:
                source_id = add_source_card(
                    user_id, original_text, title=card_title,
                    category=selected_category, card_type=selected_type,
                )

            count = 0
            blank_count = len(cards_to_save)
            for card in cards_to_save:
                if card["question"] and card["answer"]:
                    add_card(
                        user_id, card["question"], card["answer"],
                        title=card_title, category=selected_category,
                        source_id=source_id, blank_count=blank_count,
                        card_type=selected_type, rank=selected_rank,
                    )
                    count += 1

            st.success(f"{count} 枚のカードを保存しました！（原文カードも保存済み）")
            _clear_all_state()
            st.rerun()
