"""
カード追加ページ — 新規カード作成UI
"""

from __future__ import annotations

import streamlit as st

from config import BLANK_DISABLED_TYPES, CARD_TYPES, CATEGORIES, RANKS
from services.card_service import (
    apply_highlight,
    extract_highlight_keywords,
    parse_blanks_from_text,
    validate_highlight_markers,
)
from use_cases.card_workflows import save_source_with_cards

# セッション状態キー
_SK_CATEGORY = "add_card_category"
_SK_TITLE = "add_card_title"
_SK_TEXT = "add_card_text"
_SK_TYPE = "add_card_type"
_SK_RANK = "add_card_rank"
_SK_WIDGET_KEY = "widget_key_counter"
_SK_GENERATED_CARDS = "generated_cards"
_SK_PREV_MANUAL_TEXT = "prev_manual_text"


def render_add_card_page(user_id: str) -> None:
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
            "generated_cards" in st.session_state or st.session_state.add_card_text
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
        _render_no_blank_flow(
            user_id, card_title, selected_category, selected_type, selected_rank
        )
    else:
        _render_blank_flow(
            user_id, card_title, selected_category, selected_type, selected_rank
        )


def _init_session_state() -> None:
    """入力フィールドのセッションステート初期化"""
    defaults: dict[str, object] = {
        _SK_CATEGORY: "",
        _SK_TITLE: "",
        _SK_TEXT: "",
        _SK_TYPE: "",
        _SK_RANK: "B",
        _SK_WIDGET_KEY: 0,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _clear_all_state() -> None:
    """全ての関連セッション状態をクリア"""
    for key in [_SK_GENERATED_CARDS, _SK_PREV_MANUAL_TEXT]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state[_SK_CATEGORY] = ""
    st.session_state[_SK_TITLE] = ""
    st.session_state[_SK_TEXT] = ""
    st.session_state[_SK_TYPE] = ""
    st.session_state[_SK_RANK] = "B"
    st.session_state[_SK_WIDGET_KEY] += 1


def _sync_widget_to_state(widget_key: str, state_key: str) -> None:
    """on_changeコールバック: widgetの値をsession_stateにコピー"""
    st.session_state[state_key] = st.session_state[widget_key]


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
    wkey = f"category_select_{st.session_state.widget_key_counter}"
    selected_raw = st.selectbox(
        "カテゴリ",
        categories_with_placeholder,
        index=current_idx,
        key=wkey,
    )
    selected = selected_raw if selected_raw != "-- カテゴリを選択 --" else ""
    # rerun時にのみ同期（on_changeではなく毎回同期だが、selectboxの値変更以外ではrerunしない）
    st.session_state.add_card_category = selected
    return selected


def _render_rank_select() -> str:
    """ランク選択"""
    rank_idx = (
        RANKS.index(st.session_state.add_card_rank)
        if st.session_state.add_card_rank in RANKS
        else 3
    )
    wkey = f"rank_select_{st.session_state.widget_key_counter}"
    selected = st.selectbox(
        "重要度ランク",
        RANKS,
        index=rank_idx,
        key=wkey,
        help="ランクが高いものほど優先的にノルマに出題されます。",
    )
    st.session_state.add_card_rank = selected
    return selected


def _render_type_select() -> str:
    """タイプ選択"""
    types_with_placeholder = ["-- タイプを選択 --"] + CARD_TYPES
    type_idx = 0
    if st.session_state.add_card_type and st.session_state.add_card_type in CARD_TYPES:
        type_idx = types_with_placeholder.index(st.session_state.add_card_type)
    wkey = f"type_select_{st.session_state.widget_key_counter}"
    selected_raw = st.selectbox(
        "タイプ",
        types_with_placeholder,
        index=type_idx,
        key=wkey,
        help="規範/判例: 穴埋めあり、類型/知識: 穴埋めなし",
    )
    selected = selected_raw if selected_raw != "-- タイプを選択 --" else ""
    st.session_state.add_card_type = selected
    return selected


def _render_title_input() -> str:
    """タイトル入力"""
    wkey = f"title_input_{st.session_state.widget_key_counter}"
    # 初期値をwidgetキーにセット（keyが存在しない場合のみ）
    if wkey not in st.session_state:
        st.session_state[wkey] = st.session_state.add_card_title
    card_title = st.text_input(
        "カードのタイトル（共通）",
        placeholder="例: 不法行為, 契約総論",
        key=wkey,
        autocomplete="off",
        on_change=_sync_widget_to_state,
        args=(wkey, "add_card_title"),
    )
    # 同期（on_changeだけでなく初回ロード時も反映）
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
    st.subheader("① テキストとハイライト箇所を入力")
    st.info(
        f"📝 「{selected_type}」タイプ: 穴埋めなしで保存します。ハイライトしたい箇所は【】で囲んでください。"
    )

    wkey = f"text_input_{st.session_state.widget_key_counter}"
    if wkey not in st.session_state:
        st.session_state[wkey] = st.session_state.add_card_text
    source_text = st.text_area(
        "原文テキスト",
        height=200,
        placeholder="例: 民法【709条】は【不法行為】による損害賠償を規定している。",
        help="ハイライトなしで保存したい場合は【】を付けずに入力してください。",
        key=wkey,
        on_change=_sync_widget_to_state,
        args=(wkey, "add_card_text"),
    )
    st.session_state.add_card_text = source_text

    marker_is_valid = True
    marker_message = ""
    if source_text:
        marker_is_valid, marker_message, _count = validate_highlight_markers(
            source_text
        )
        if marker_is_valid:
            _render_highlight_preview(source_text)
        else:
            st.warning(marker_message)

    if st.button("💾 保存", type="primary", key="save_no_blank_btn"):
        if not source_text:
            st.warning("テキストを入力してください。")
        elif not marker_is_valid:
            st.warning(marker_message)
        else:
            highlighted_keywords = extract_highlight_keywords(source_text)
            save_source_with_cards(
                user_id,
                source_text=source_text,
                title=card_title,
                category=selected_category,
                card_type=selected_type,
                cards=[
                    {
                        "question": source_text,
                        "answer": "",
                        "title": card_title,
                        "category": selected_category,
                        "blank_count": 0,
                        "card_type": selected_type,
                        "rank": selected_rank,
                        "highlighted_keywords": highlighted_keywords,
                    }
                ],
            )
            st.success("保存しました！")
            _clear_all_state()
            st.rerun()


def _render_highlight_preview(text: str, keywords: str = "") -> None:
    """知識・類型カードの表示プレビューを描画する。"""
    if not text:
        return

    marker_is_valid, marker_message, _count = validate_highlight_markers(text)
    if not marker_is_valid:
        st.warning(marker_message)
        return

    preview_q = apply_highlight(text, keywords)
    st.markdown(
        f"<div style='font-size: 0.9em; padding: 12px; margin-bottom: 20px; background-color: #f9fafb; border-radius: 4px; border-left: 4px solid #3b82f6;'><strong>ハイライト表示プレビュー:</strong> <br/> {preview_q}</div>",
        unsafe_allow_html=True,
    )


def _render_blank_flow(
    user_id: str,
    card_title: str,
    selected_category: str,
    selected_type: str,
    selected_rank: str,
) -> None:
    """穴埋めありタイプ（規範/判例/未選択）のフロー"""
    st.subheader("① テキストを入力")

    st.info("💡 穴埋めにしたい箇所を【】で囲んでください。例: 民法【709条】は...")

    wkey = f"text_input_{st.session_state.widget_key_counter}"
    if wkey not in st.session_state:
        st.session_state[wkey] = st.session_state.add_card_text
    source_text = st.text_area(
        "",
        height=200,
        placeholder="例: 民法【709条】は【不法行為】による【損害賠償】を規定している。",
        key=wkey,
        label_visibility="collapsed",
        on_change=_sync_widget_to_state,
        args=(wkey, "add_card_text"),
    )
    st.session_state.add_card_text = source_text

    # テキストが変更されたら生成済みカードをクリア
    if "generated_cards" in st.session_state:
        prev_text = st.session_state.get("prev_manual_text", "")
        if source_text != prev_text:
            del st.session_state.generated_cards
            st.info("テキストが変更されました。再度「カード生成」を押してください。")
    st.session_state.prev_manual_text = source_text

    _render_manual_generate(source_text)

    # プレビュー＆保存
    if "generated_cards" in st.session_state:
        _render_save_form(
            user_id, card_title, selected_category, selected_type, selected_rank
        )


def _render_manual_generate(source_text: str) -> None:
    """カード生成"""
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
                st.error(
                    "カードの生成に失敗しました。【】で穴埋め箇所を正しく指定してください。"
                )


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
                q = st.text_input(
                    "問題",
                    value=card["question"],
                    key=f"q_{i}",
                    label_visibility="collapsed",
                    placeholder="問題",
                )
            with col2:
                a = st.text_input(
                    "答え",
                    value=card["answer"],
                    key=f"a_{i}",
                    label_visibility="collapsed",
                    placeholder="答え",
                )
            cards_to_save.append({"question": q, "answer": a})

            st.markdown("---")

        if st.form_submit_button("💾 デッキに保存", type="primary"):
            original_text = st.session_state.get("add_card_text", "")
            cards_payload = []
            blank_count = len(cards_to_save)
            for card in cards_to_save:
                if card["question"] and card["answer"]:
                    cards_payload.append(
                        {
                            "question": card["question"],
                            "answer": card["answer"],
                            "title": card_title,
                            "category": selected_category,
                            "blank_count": blank_count,
                            "card_type": selected_type,
                            "rank": selected_rank,
                        }
                    )

            result = save_source_with_cards(
                user_id,
                source_text=original_text,
                title=card_title,
                category=selected_category,
                card_type=selected_type,
                cards=cards_payload,
            )

            st.success(
                f"{result.card_count} 枚のカードを保存しました！（原文カードも保存済み）"
            )
            _clear_all_state()
            st.rerun()
