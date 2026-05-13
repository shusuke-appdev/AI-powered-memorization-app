"""
ログインページ — 認証UI
"""

from __future__ import annotations

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth import create_session, get_all_users, login_user_direct, register_user


def show_login_page(cookie_controller: CookieController) -> None:
    """ログイン/登録ページを表示"""
    st.title("🧠 AI 暗記カード")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### ログイン")

        login_tab, register_tab = st.tabs(["ログイン", "新規登録"])

        with login_tab:
            _render_login_form(cookie_controller)

        with register_tab:
            _render_register_form(cookie_controller)


def _render_login_form(cookie_controller: CookieController) -> None:
    """ログインフォームを表示"""
    users = get_all_users()
    if not users:
        st.info("登録されているユーザーがいません。「新規登録」タブからユーザーを作成してください。")
        return

    st.markdown("アカウントを選択してログインしてください：")
    for user in users:
        if st.button(f"👤 {user['username']}", key=f"login_btn_{user['id']}", use_container_width=True):
            success, message, user_id = login_user_direct(user['id'])
            if success:
                st.session_state.user_id = user_id
                st.session_state.username = user['username']

                token = create_session(user_id)
                cookie_controller.set(
                    "session_token", token, max_age=30 * 24 * 60 * 60
                )

                st.success(message)
                st.rerun()
            else:
                st.error(message)


def _render_register_form(cookie_controller: CookieController) -> None:
    """新規登録フォームを表示"""
    with st.form("register_form"):
        new_username = st.text_input("ユーザー名", key="register_username")
        new_api_key = st.text_input(
            "Gemini APIキー (任意)",
            type="password",
            key="register_api_key",
            help="AIチャットを利用する場合は入力してください",
        )

        if st.form_submit_button("登録", type="primary", use_container_width=True):
            success, message, user_id = register_user(
                new_username, new_api_key
            )
            if success:
                st.session_state.user_id = user_id
                st.session_state.username = new_username

                token = create_session(user_id)
                cookie_controller.set(
                    "session_token", token, max_age=30 * 24 * 60 * 60
                )

                st.success(message)
                st.rerun()
            else:
                st.error(message)
