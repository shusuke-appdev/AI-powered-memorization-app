"""
AI 暗記カード — メインエントリーポイント

2595行のモノリシックコードから、ページ別・サービス別に分割された
クリーンアーキテクチャへリファクタリング済み。
"""

from __future__ import annotations

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth import get_api_key, get_username, validate_session_token
from database import DatabaseConnectionError
from pages.add_card_page import render_add_card_page
from pages.listen_page import render_listen_page
from pages.login_page import show_login_page
from pages.manage_page import render_manage_page
from pages.review_page import render_review_page
from pages.sidebar import render_sidebar
from pages.stats_page import render_stats_page
from styles import apply_base_styles

# ============ Page Config ============

st.set_page_config(page_title="AI 暗記カード", page_icon="🧠", layout="wide")

# Cookie Controller——シングルトンで予期しないrerunを防止
if "cookie_controller" not in st.session_state:
    st.session_state.cookie_controller = CookieController()
cookie_controller = st.session_state.cookie_controller

# ベーススタイルを適用
apply_base_styles()


# ============ 認証 ============


def check_auth() -> bool:
    """認証状態をチェック"""
    if "user_id" in st.session_state and st.session_state.user_id:
        return True

    session_token = cookie_controller.get("session_token")
    if session_token:
        user_id = validate_session_token(session_token)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.username = get_username(user_id)
            return True

    return False


# ============ メインアプリ ============


def show_main_app() -> None:
    """メインアプリケーションを表示"""
    user_id: str = st.session_state.user_id
    username: str = st.session_state.get("username", "ユーザー")
    api_key: str = get_api_key(user_id)

    # サイドバー
    render_sidebar(user_id, username, api_key)

    # タイトル
    st.title("🧠 AI 暗記カード")

    # Tab Navigation
    tab1, tab2, tab5, tab3, tab4 = st.tabs(
        ["📚 本日のノルマ", "📝 カードを追加", "🎧 聞き流し", "🗂️ カード管理", "📊 統計"]
    )

    with tab1:
        render_review_page(user_id, api_key)

    with tab2:
        render_add_card_page(user_id, api_key)

    with tab5:
        render_listen_page(user_id)

    with tab3:
        render_manage_page(user_id)

    with tab4:
        render_stats_page(user_id)


# ============ アプリケーション実行 ============

try:
    if check_auth():
        show_main_app()
    else:
        show_login_page(cookie_controller)
except DatabaseConnectionError as e:
    st.error(f"⚠️ {e.message}")
    st.info("🔄 ページを再読み込みしてください。問題が続く場合は、しばらく待ってから再試行してください。")
    if st.button("再読み込み"):
        from database import reset_connection

        reset_connection()
        st.rerun()
except Exception:
    st.error("予期しないエラーが発生しました。")
    st.info("🔄 ページを再読み込みするか、サポートにお問い合わせください。")
    if st.button("再読み込み"):
        st.rerun()
