"""認証後に選択された1画面だけを実行する上部ナビゲーション。"""

from __future__ import annotations

from functools import partial

import streamlit as st

from pages.add_card_page import render_add_card_page
from pages.listen_page import render_listen_page
from pages.login_page import show_login_page
from pages.manage_page import render_manage_page
from pages.review_page import render_review_page
from pages.stats_page import render_stats_page


def build_authenticated_pages(user_id: str) -> list[st.Page]:
    """固定URLを持つ認証後ページを返す。"""
    return [
        st.Page(
            partial(render_review_page, user_id),
            title="本日のノルマ",
            icon="📚",
            url_path="review",
            default=True,
        ),
        st.Page(
            partial(render_add_card_page, user_id),
            title="カードを追加",
            icon="📝",
            url_path="add",
        ),
        st.Page(
            partial(render_listen_page, user_id),
            title="聞き流し",
            icon="🎧",
            url_path="listen",
        ),
        st.Page(
            partial(render_manage_page, user_id),
            title="カード管理",
            icon="🗂️",
            url_path="manage",
        ),
        st.Page(
            partial(render_stats_page, user_id),
            title="統計",
            icon="📊",
            url_path="stats",
        ),
    ]


def build_login_pages() -> list[st.Page]:
    """未認証中も固定URLを解決し、選択URL上でログイン画面だけを表示する。"""
    pages = []
    for title, path, is_default in (
        ("ログイン", "review", True),
        ("ログイン", "add", False),
        ("ログイン", "listen", False),
        ("ログイン", "manage", False),
        ("ログイン", "stats", False),
    ):
        pages.append(
            st.Page(
                show_login_page,
                title=title,
                url_path=path,
                default=is_default,
            )
        )
    return pages
