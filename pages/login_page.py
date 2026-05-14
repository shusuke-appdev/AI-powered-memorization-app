"""
ログインページ — 認証UI
"""

from __future__ import annotations

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth import (
    create_session,
    get_all_users,
    login_user_direct,
    register_user,
)


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


def _set_login_session(
    cookie_controller: CookieController, user_id: str, username: str | None
) -> None:
    """ログイン成功後のセッションを保存"""
    st.session_state.user_id = user_id
    st.session_state.username = username or "ユーザー"

    token = create_session(user_id)
    cookie_controller.set("session_token", token, max_age=30 * 24 * 60 * 60)


def _render_login_form(cookie_controller: CookieController) -> None:
    """ユーザー選択ログインを表示"""
    users = get_all_users()
    if not users:
        st.info("登録されているユーザーがいません。「新規登録」タブからユーザーを作成してください。")
        return

    st.markdown("アカウントを選択してログインしてください：")
    for user in users:
        if st.button(f"👤 {user['username']}", key=f"login_btn_{user['id']}", use_container_width=True):
            success, message, user_id = login_user_direct(user['id'])
            if success:
                _set_login_session(cookie_controller, user_id, user["username"])
                st.success(message)
                st.rerun()
            else:
                st.error(message)


def _render_register_form(cookie_controller: CookieController) -> None:
    """新規登録フォームを表示"""
    with st.form("register_form"):
        new_username = st.text_input("ユーザー名", key="register_username")

        if st.form_submit_button("登録", type="primary", use_container_width=True):
            success, message, user_id = register_user(new_username)
            if success:
                _set_login_session(cookie_controller, user_id, new_username)
                st.success(message)
                st.rerun()
            else:
                st.error(message)
