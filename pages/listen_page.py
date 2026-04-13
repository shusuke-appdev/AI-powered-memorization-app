"""
聞き流しページ — 音声再生UI
"""

from __future__ import annotations

import random

import streamlit as st

from components import render_audio_player
from config import CATEGORIES
from storage import load_source_cards


def render_listen_page(user_id: str) -> None:
    """聞き流しタブを表示"""
    st.header("🎧 聞き流しモード")
    st.markdown("教科を選択して、原文の音声を聞き流すことができます。")

    selected_category = st.selectbox("教科を選択", CATEGORIES, key="audio_category")

    if st.button("▶️ 再生リストを作成・再生", type="primary"):
        source_cards_all = load_source_cards(user_id)
        playlist = [
            {"id": s["id"], "text": s["source_text"], "title": s.get("title", "")}
            for s in source_cards_all
            if s.get("category") == selected_category
        ]

        if not playlist:
            st.warning(f"「{selected_category}」の原文カードがありません。")
        else:
            random.shuffle(playlist)
            st.success(f"全{len(playlist)}件の再生リストを作成しました。")
            render_audio_player(playlist)
