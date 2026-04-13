"""
ログインページ — 認証UI
"""

from __future__ import annotations

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth import authenticate_user, create_session, register_user


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
    with st.form("login_form"):
        username = st.text_input("ユーザー名", key="login_username")
        password = st.text_input("パスワード", type="password", key="login_password")

        if st.form_submit_button("ログイン", type="primary", use_container_width=True):
            success, message, user_id = authenticate_user(username, password)
            if success:
                st.session_state.user_id = user_id
                st.session_state.username = username

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
        new_password = st.text_input(
            "パスワード", type="password", key="register_password"
        )
        confirm_password = st.text_input(
            "パスワード（確認）", type="password", key="confirm_password"
        )
        new_api_key = st.text_input(
            "Gemini APIキー",
            type="password",
            key="register_api_key",
            help="Google GeminiのAPIキーを入力してください",
        )

        if st.form_submit_button("登録", type="primary", use_container_width=True):
            if new_password != confirm_password:
                st.error("パスワードが一致しません")
            else:
                success, message, user_id = register_user(
                    new_username, new_password, new_api_key
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
