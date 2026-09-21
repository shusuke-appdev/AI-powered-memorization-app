"""
サイドバーモジュール — ユーザー情報・設定
"""

from __future__ import annotations

import streamlit as st

from auth import get_daily_quota_limit, update_daily_quota_limit
from services.session_service import queue_cookie_remove, reset_user_session_state


def render_sidebar(user_id: str, username: str) -> None:
    """サイドバーを表示"""
    with st.sidebar:
        st.markdown(f"### 👤 {username} さん")

        _render_quota_section(user_id)

        st.markdown("---")
        st.button(
            "🚪 ログアウト",
            width="stretch",
            key="sidebar_logout",
            type="primary",
            on_click=_logout,
        )


def _update_quota(user_id: str, previous_quota: int) -> None:
    """ノルマ変更をウィジェットの標準更新内で反映する。"""
    new_quota = int(st.session_state.sidebar_quota)
    if new_quota != previous_quota:
        update_daily_quota_limit(user_id, new_quota)
        st.session_state.quota_card_ids = None


def _render_quota_section(user_id: str) -> None:
    """ノルマ設定セクション"""
    col_label, col_input = st.columns([1, 1])
    with col_label:
        st.markdown("##### 📊 ノルマ")
    with col_input:
        current_quota = get_daily_quota_limit(user_id)
        st.number_input(
            "上限",
            min_value=1,
            max_value=100,
            value=current_quota,
            step=1,
            key="sidebar_quota",
            label_visibility="collapsed",
            on_change=_update_quota,
            args=(user_id, current_quota),
        )


def _logout() -> None:
    """ログアウト処理"""
    from auth import delete_session

    cookie_controller = st.session_state.get("cookie_controller")
    if cookie_controller:
        session_token = cookie_controller.get("session_token")
        if session_token:
            delete_session(session_token)

    reset_user_session_state(st.session_state)
    queue_cookie_remove(st.session_state, "session_token")
    st.session_state["_force_logged_out_once"] = True
