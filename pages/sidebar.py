"""
サイドバーモジュール — ユーザー情報・設定・ヘルプAI
"""

from __future__ import annotations

import streamlit as st

from auth import get_daily_quota_limit, update_api_key, update_daily_quota_limit
from services.ai_service import help_chat
from styles import apply_dark_mode_styles


def render_sidebar(user_id: str, username: str, api_key: str) -> None:
    """サイドバーを表示"""
    with st.sidebar:
        st.markdown(f"### 👤 {username} さん")

        _render_dark_mode_toggle()
        st.markdown("---")
        _render_api_key_section(user_id, api_key)
        st.markdown("---")
        _render_quota_section(user_id)
        st.markdown("---")
        _render_help_chat(api_key)

        st.markdown("---")
        if st.button("🚪 ログアウト", use_container_width=True, key="sidebar_logout", type="primary"):
            _logout()


def _render_dark_mode_toggle() -> None:
    """ダークモードトグル"""
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False

    if st.session_state.dark_mode:
        if st.button("☀️ ライトモードに切替", key="theme_toggle", use_container_width=True):
            st.session_state.dark_mode = False
            st.rerun()
    else:
        if st.button("🌙 ダークモードに切替", key="theme_toggle", use_container_width=True):
            st.session_state.dark_mode = True
            st.rerun()

    if st.session_state.dark_mode:
        apply_dark_mode_styles()


def _render_api_key_section(user_id: str, user_api_key: str) -> None:
    """APIキー設定セクション"""
    st.markdown("##### ⚙️ APIキー設定")
    if user_api_key:
        st.success("✅ 設定済み")
        with st.expander("キーを変更", expanded=False):
            new_api_key = st.text_input("新しいAPIキー", type="password", placeholder="AIza...", key="sidebar_api_key_input")
            if st.button("更新", key="sidebar_update_api"):
                if new_api_key:
                    update_api_key(user_id, new_api_key)
                    st.success("更新しました！")
                    st.rerun()
    else:
        st.warning("⚠️ 未設定")
        new_api_key = st.text_input("Gemini APIキー", type="password", placeholder="AIza...", key="sidebar_set_api_key")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("保存", key="sidebar_save_api"):
                if new_api_key:
                    update_api_key(user_id, new_api_key)
                    st.success("保存しました！")
                    st.rerun()
        with col2:
            st.markdown("[🔗 取得](https://aistudio.google.com/)")


def _render_quota_section(user_id: str) -> None:
    """ノルマ設定セクション"""
    col_label, col_input = st.columns([1, 1])
    with col_label:
        st.markdown("##### 📊 ノルマ")
    with col_input:
        current_quota = get_daily_quota_limit(user_id)
        new_quota = st.number_input(
            "上限", min_value=1, max_value=100, value=current_quota,
            step=1, key="sidebar_quota", label_visibility="collapsed",
        )
        if new_quota != current_quota:
            update_daily_quota_limit(user_id, new_quota)
            st.session_state.quota_card_ids = None
            st.rerun()


def _render_help_chat(api_key: str) -> None:
    """ヘルプAIチャットセクション"""
    st.markdown("<div class='help-ai-title'>🤖 ヘルプAI</div>", unsafe_allow_html=True)

    if "help_chat_history" not in st.session_state:
        st.session_state.help_chat_history = []

    chat_container = st.container(height=450)
    with chat_container:
        if not st.session_state.help_chat_history:
            st.markdown(
                "<div style='color: #6b7280; font-size: 13px; padding: 10px;'>💬 アプリの使い方について質問してください</div>",
                unsafe_allow_html=True,
            )
        else:
            for msg in st.session_state.help_chat_history:
                if msg["role"] == "user":
                    st.markdown(f"<div class='chat-message user'>🧑 {msg['content']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='chat-message assistant'>🤖 {msg['content']}</div>", unsafe_allow_html=True)

    with st.form(key="help_chat_form", clear_on_submit=True):
        user_question = st.text_area(
            "質問を入力", placeholder="質問を入力... (Ctrl+Enterで送信)",
            key="help_question_input", label_visibility="collapsed", height=215,
        )
        submitted = st.form_submit_button("送信", use_container_width=True)

        if submitted and user_question and user_question.strip():
            if not api_key:
                st.error("APIキーを設定してください")
            else:
                st.session_state.help_chat_history.append({"role": "user", "content": user_question})
                with st.spinner("回答中..."):
                    result = help_chat(user_question, api_key, st.session_state.help_chat_history[:-1])
                if result["success"]:
                    st.session_state.help_chat_history.append({"role": "assistant", "content": result["response"]})
                else:
                    st.session_state.help_chat_history.append({"role": "assistant", "content": f"⚠️ {result['error']}"})
                st.rerun()

    if st.session_state.help_chat_history:
        if st.button("🗑️ 履歴クリア", key="clear_chat"):
            st.session_state.help_chat_history = []
            st.rerun()


def _logout() -> None:
    """ログアウト処理"""
    from streamlit_cookies_controller import CookieController

    from auth import delete_session

    cookie_controller = CookieController()
    session_token = cookie_controller.get("session_token")
    if session_token:
        delete_session(session_token)
        cookie_controller.remove("session_token")

    for key in ("user_id", "username"):
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()
