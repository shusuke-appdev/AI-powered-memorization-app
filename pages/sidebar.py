"""
サイドバーモジュール — ユーザー情報・設定
"""

from __future__ import annotations

import streamlit as st

from auth import get_daily_quota_limit, update_daily_quota_limit
from styles import apply_dark_mode_styles


def render_sidebar(user_id: str, username: str) -> None:
    """サイドバーを表示"""
    with st.sidebar:
        st.markdown(f"### 👤 {username} さん")

        _render_dark_mode_toggle()
        st.markdown("---")
        _render_quota_section(user_id)

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


def _logout() -> None:
    """ログアウト処理"""
    import time

    from auth import delete_session

    cookie_controller = st.session_state.get("cookie_controller")
    if cookie_controller:
        session_token = cookie_controller.get("session_token")
        if session_token:
            delete_session(session_token)
            cookie_controller.remove("session_token")
            time.sleep(0.5)  # クッキー削除の反映を待つ

    for key in ("user_id", "username", "cookie_controller"):
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()
