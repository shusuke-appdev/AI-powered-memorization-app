"""
ログインページ — 認証UI
"""

from __future__ import annotations

import streamlit as st

from auth import (
    create_session,
    get_all_users,
    login_user_direct,
    register_user,
)
from services.session_service import queue_cookie_set, reset_user_session_state


def show_login_page() -> None:
    """ログイン/登録ページを表示"""
    st.title("🧠 AI 暗記カード")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### ログイン")

        login_tab, register_tab = st.tabs(["ログイン", "新規登録"])

        with login_tab:
            _render_login_form()

        with register_tab:
            _render_register_form()


def _set_login_session(user_id: str, username: str | None) -> None:
    """ログイン成功後のセッションを保存"""
    reset_user_session_state(st.session_state)
    st.session_state.user_id = user_id
    st.session_state.username = username or "ユーザー"

    token = create_session(user_id)
    queue_cookie_set(
        st.session_state,
        "session_token",
        token,
        max_age=30 * 24 * 60 * 60,
    )


def _login(user_id: str, username: str) -> None:
    """選択ユーザーでログインするボタンコールバック。"""
    success, message, authenticated_user_id = login_user_direct(user_id)
    if success:
        _set_login_session(authenticated_user_id, username)
    else:
        st.session_state["login_error"] = message


def _render_login_form() -> None:
    """ユーザー選択ログインを表示"""
    users = get_all_users()
    if not users:
        st.info(
            "登録されているユーザーがいません。「新規登録」タブからユーザーを作成してください。"
        )
        return

    st.markdown("アカウントを選択してログインしてください：")
    for user in users:
        st.button(
            f"👤 {user['username']}",
            key=f"login_btn_{user['id']}",
            width="stretch",
            on_click=_login,
            args=(user["id"], user["username"]),
        )

    if error := st.session_state.pop("login_error", None):
        st.error(error)


def _register() -> None:
    """ユーザー登録とログインを1回で行うコールバック。"""
    username = st.session_state.get("register_username", "")
    success, message, user_id = register_user(username)
    if success:
        _set_login_session(user_id, username)
    else:
        st.session_state["register_error"] = message


def _render_register_form() -> None:
    """新規登録フォームを表示"""
    with st.form("register_form"):
        st.text_input("ユーザー名", key="register_username")

        st.form_submit_button(
            "登録",
            type="primary",
            width="stretch",
            on_click=_register,
        )

    if error := st.session_state.pop("register_error", None):
        st.error(error)
