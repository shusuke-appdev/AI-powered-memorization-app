"""
AI 暗記カード — メインエントリーポイント

2595行のモノリシックコードから、ページ別・サービス別に分割された
クリーンアーキテクチャへリファクタリング済み。
"""

from __future__ import annotations

import logging
import uuid

import streamlit as st
from streamlit_cookies_controller import CookieController

from application_errors import ApplicationError
from auth import get_username, validate_session_token
from database import (
    DatabaseConnectionError,
    as_database_connection_error,
    reset_connection,
)
from pages.navigation import build_authenticated_pages, build_login_pages
from pages.sidebar import render_sidebar
from services.session_service import (
    flush_pending_cookie_action,
    reset_user_session_state,
)
from styles import apply_base_styles

logger = logging.getLogger(__name__)

# ============ Page Config ============

st.set_page_config(page_title="AI 暗記カード", page_icon="🧠", layout="wide")

# Cookie Controller——シングルトンで予期しないrerunを防止
if "cookie_controller" not in st.session_state:
    st.session_state.cookie_controller = CookieController()
cookie_controller = st.session_state.cookie_controller
flush_pending_cookie_action(st.session_state, cookie_controller)

# ベーススタイルを適用
apply_base_styles()


# ============ 認証 ============


def check_auth() -> bool:
    """認証状態をチェック"""
    if st.session_state.pop("_force_logged_out_once", False):
        return False
    if "user_id" in st.session_state and st.session_state.user_id:
        return True

    session_token = cookie_controller.get("session_token")
    if session_token:
        user_id = validate_session_token(session_token)
        if user_id:
            reset_user_session_state(st.session_state)
            st.session_state.user_id = user_id
            st.session_state.username = get_username(user_id)
            return True

    return False


# ============ メインアプリ ============


def show_main_app() -> None:
    """メインアプリケーションを表示"""
    user_id: str = st.session_state.user_id
    username: str = st.session_state.get("username", "ユーザー")

    # サイドバー
    render_sidebar(user_id, username)

    st.navigation(build_authenticated_pages(user_id), position="top").run()


def show_database_error(error: DatabaseConnectionError) -> None:
    """データベース接続エラーと再読み込み操作を表示する。"""
    st.error(f"⚠️ {error.message}")
    st.info(
        "🔄 ページを再読み込みしてください。問題が続く場合は、しばらく待ってから再試行してください。"
    )
    if st.button("再読み込み"):
        reset_connection()
        st.rerun()


# ============ アプリケーション実行 ============

try:
    if check_auth():
        show_main_app()
    else:
        st.navigation(build_login_pages(), position="hidden").run()
except DatabaseConnectionError as e:
    show_database_error(e)
except ApplicationError as e:
    st.error(f"⚠️ {e.user_message}")
    st.info("🔄 内容を確認して、もう一度お試しください。")
except Exception as e:
    database_error = as_database_connection_error(e)
    if database_error is not None:
        show_database_error(database_error)
    else:
        error_reference = uuid.uuid4().hex[:8]
        logger.error(
            "Unhandled application error reference=%s type=%s",
            error_reference,
            type(e).__name__,
        )
        st.error(
            "予期しないエラーが発生しました。"
            f"時間をおいて再試行してください（参照: {error_reference}）。"
        )
        st.info("🔄 ページを再読み込みするか、サポートにお問い合わせください。")
        if st.button("再読み込み"):
            st.rerun()
