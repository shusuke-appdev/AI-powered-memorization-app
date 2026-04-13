"""
統計ページ — 学習統計・データ管理UI
"""

from __future__ import annotations

import streamlit as st

from export_import import render_export_import_ui
from stats import calculate_statistics, render_statistics_ui
from storage import add_card, add_source_card, load_cards, load_source_cards


def render_stats_page(user_id: str) -> None:
    """統計・データ管理タブを表示"""
    st.title("📊 統計・データ管理")

    all_cards = load_cards(user_id)
    all_source_cards = load_source_cards(user_id)

    st.subheader("📈 学習統計")
    stats = calculate_statistics(all_cards, all_source_cards)
    render_statistics_ui(stats, st)

    st.markdown("---")

    render_export_import_ui(
        user_id, all_cards, all_source_cards, st, add_card, add_source_card
    )
