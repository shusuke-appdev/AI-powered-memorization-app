"""
統計・データ管理ページ — 学習統計UI + エクスポート/インポートUI
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from export_import import (
    export_cards_csv,
    export_cards_json,
    import_cards_csv,
    import_cards_json,
)
from stats import calculate_statistics
from storage import add_card, add_source_card, load_cards, load_source_cards


def render_stats_page(user_id: str) -> None:
    """統計・データ管理タブを表示"""
    st.title("📊 統計・データ管理")

    all_cards = load_cards(user_id)
    all_source_cards = load_source_cards(user_id)

    st.subheader("📈 学習統計")
    stats = calculate_statistics(all_cards, all_source_cards)
    _render_statistics_ui(stats)

    st.markdown("---")

    _render_export_import_ui(user_id, all_cards, all_source_cards)


# ============ 統計UI ============


def _render_statistics_ui(stats: dict[str, Any]) -> None:
    """Streamlit UIで統計を表示"""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 総カード数", stats["total_cards"])
    with col2:
        st.metric("✅ 習得済み", stats["mastered_cards"], help="連続5回以上正解したカード数")
    with col3:
        st.metric("📖 学習中", stats["learning_cards"], help="学習開始済みだが習得に達していないカード数")
    with col4:
        st.metric("📅 本日復習", stats["due_today"])

    if stats["total_cards"] > 0:
        st.progress(
            stats["mastery_rate"] / 100,
            text=f"習得率: {stats['mastery_rate']}% （習得済み / 総カード数）",
        )

    st.markdown("**全体の難易度分布**")
    st.caption("簡単：十分な連続正解があり定着しているカード / 普通：学習初期のカード / 難しい：復習間隔が詰まっている苦手カード")
    diff = stats["difficulty_distribution"]
    st.markdown(f"🟢 簡単: {diff['easy']} | 🟡 普通: {diff['medium']} | 🔴 難しい: {diff['hard']}")

    st.markdown("---")

    if stats["category_stats"]:
        st.subheader("📊 教科別 達成状況")
        categories = list(stats["category_stats"].items())
        cols = st.columns(4, gap="small")
        for idx, (cat_name, cat_data) in enumerate(categories):
            with cols[idx % 4]:
                _render_category_chart(cat_name, cat_data)


def _render_category_chart(category: str, data: dict[str, Any]) -> None:
    """個別のカテゴリエリアを描画"""
    st.markdown(f"**{category}**")

    total = data["total"]
    mastery = round(data["mastered"] / total * 100, 1) if total > 0 else 0
    st.caption(f"総数: {total}枚 | 習得率: {mastery}% | 復習待ち: {data['due']}枚")

    diff_data = data["difficulty"]

    chart_df = pd.DataFrame([
        {"Status": "簡単", "Count": diff_data["easy"]},
        {"Status": "普通", "Count": diff_data["medium"]},
        {"Status": "難しい", "Count": diff_data["hard"]},
    ])

    chart_df = chart_df[chart_df["Count"] > 0]

    if not chart_df.empty:
        # 難易度ごとの色を正しく適用（修正: 全セグメント同色問題を解消）
        color_map = {"簡単": "#10b981", "普通": "#f59e0b", "難しい": "#ef4444"}

        fig = px.pie(
            chart_df,
            values="Count",
            names="Status",
            color="Status",
            color_discrete_map=color_map,
            hole=0.4,
        )

        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=200,
            showlegend=False,
            annotations=[
                dict(
                    text=category,
                    x=0.5,
                    y=0.5,
                    font_size=14,
                    showarrow=False,
                )
            ],
        )
        fig.update_traces(textposition="inside", textinfo="percent", textfont_color="white")

        st.plotly_chart(fig, use_container_width=True, key=f"chart_{category}")
    else:
        st.info("データがありません")


# ============ エクスポート/インポートUI ============


def _render_export_import_ui(
    user_id: str,
    cards: list[dict[str, Any]],
    source_cards: list[dict[str, Any]],
) -> None:
    """エクスポート/インポートのUIを表示"""
    st.markdown("### 📦 データ管理")

    export_tab, import_tab = st.tabs(["📥 エクスポート", "📤 インポート"])

    with export_tab:
        st.markdown("カードデータをダウンロードしてバックアップできます。")

        col1, col2 = st.columns(2)
        with col1:
            # JSONエクスポート
            json_data = export_cards_json(cards, source_cards)
            st.download_button(
                label="📥 JSONでダウンロード",
                data=json_data,
                file_name=f"flashcards_{date.today().isoformat()}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col2:
            # CSVエクスポート
            csv_data = export_cards_csv(cards)
            st.download_button(
                label="📥 CSVでダウンロード",
                data=csv_data,
                file_name=f"flashcards_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.info(f"📊 カード数: {len(cards)}枚 / 原文カード: {len(source_cards)}件")

    with import_tab:
        st.markdown("バックアップファイルからカードを復元できます。")

        uploaded_file = st.file_uploader(
            "ファイルを選択", type=["json", "csv"], key="import_file_uploader"
        )

        col1, col2 = st.columns(2)
        with col1:
            duplicate_action = st.radio(
                "重複時の処理",
                ["skip", "create_duplicate"],
                format_func=lambda x: "スキップ" if x == "skip" else "重複として追加",
                horizontal=True,
                key="import_duplicate_action",
            )
        with col2:
            reset_progress = st.checkbox(
                "学習進捗をリセット", value=True, key="import_reset_progress"
            )

        if uploaded_file is not None:
            file_content = uploaded_file.read().decode("utf-8")
            file_type = uploaded_file.name.split(".")[-1].lower()

            if st.button("📤 インポート実行", type="primary", use_container_width=True):
                if file_type == "json":
                    result = import_cards_json(file_content, cards, duplicate_action)
                else:
                    result = import_cards_csv(
                        file_content, cards, duplicate_action, reset_progress
                    )

                if result["error"]:
                    st.error(result["error"])
                else:
                    imported_count = 0
                    for card in result["cards"]:
                        add_card(
                            user_id,
                            card["question"],
                            card["answer"],
                            title=card.get("title", ""),
                            category=card.get("category", "その他"),
                        )
                        imported_count += 1

                    # 原文カードもインポート（JSONの場合）
                    source_imported = 0
                    if file_type == "json" and result.get("source_cards"):
                        for sc in result["source_cards"]:
                            add_source_card(
                                user_id,
                                sc.get("source_text", ""),
                                title=sc.get("title", ""),
                                category=sc.get("category", "その他"),
                            )
                            source_imported += 1

                    st.success(f"✅ {imported_count}枚のカードをインポートしました！")
                    if result["skipped"] > 0:
                        st.info(
                            f"📋 {result['skipped']}枚の重複カードをスキップしました。"
                        )
                    if source_imported > 0:
                        st.info(
                            f"📄 {source_imported}件の原文カードもインポートしました。"
                        )
                    st.rerun()
