"""
統計モジュール - 学習統計の計算と表示（重複ロジック排除版）
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Any

import pandas as pd
import plotly.express as px

from config import MASTERY_THRESHOLD

# ============ 難易度判定（共通関数） ============


def classify_difficulty(ease_factor: float, repetitions: int) -> str:
    """
    カードの難易度を分類

    Args:
        ease_factor: SM-2のEase Factor
        repetitions: 連続正解回数

    Returns:
        "easy" | "medium" | "hard"
    """
    if repetitions == 0:
        return "medium"
    if ease_factor < 2.0 or (ease_factor < 2.5 and repetitions < 2):
        return "hard"
    if ease_factor >= 2.5 and repetitions >= 3:
        return "easy"
    return "medium"


# ============ 統計計算 ============


def calculate_statistics(
    cards: list[dict[str, Any]], source_cards: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    カードデータから学習統計を計算

    Args:
        cards: 暗記カードのリスト
        source_cards: 原文カードのリスト（オプション）

    Returns:
        dict: 統計データ
    """
    if not cards:
        return {
            "total_cards": 0,
            "total_source_cards": len(source_cards) if source_cards else 0,
            "mastered_cards": 0,
            "learning_cards": 0,
            "new_cards": 0,
            "due_today": 0,
            "category_stats": {},
            "difficulty_distribution": {"easy": 0, "medium": 0, "hard": 0},
            "average_ease_factor": 2.5,
            "mastery_rate": 0,
        }

    today = datetime.date.today().isoformat()

    total_cards = len(cards)
    mastered_cards = sum(1 for c in cards if c.get("repetitions", 0) >= MASTERY_THRESHOLD)
    learning_cards = sum(1 for c in cards if 0 < c.get("repetitions", 0) < MASTERY_THRESHOLD)
    new_cards = sum(1 for c in cards if c.get("repetitions", 0) == 0)
    due_today = sum(1 for c in cards if c.get("next_review", "") <= today)

    # カテゴリ別統計
    category_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "mastered": 0,
            "due": 0,
            "difficulty": {"easy": 0, "medium": 0, "hard": 0},
        }
    )

    difficulty_distribution: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    total_ease = 0.0

    for card in cards:
        category = card.get("category", "その他")
        ef = card.get("ease_factor", 2.5)
        reps = card.get("repetitions", 0)
        total_ease += ef

        category_stats[category]["total"] += 1

        if reps >= MASTERY_THRESHOLD:
            category_stats[category]["mastered"] += 1
        if card.get("next_review", "") <= today:
            category_stats[category]["due"] += 1

        # 難易度判定（共通関数を使用 — 重複排除）
        diff_level = classify_difficulty(ef, reps)
        category_stats[category]["difficulty"][diff_level] += 1
        difficulty_distribution[diff_level] += 1

    average_ease_factor = total_ease / total_cards if total_cards > 0 else 2.5

    return {
        "total_cards": total_cards,
        "total_source_cards": len(source_cards) if source_cards else 0,
        "mastered_cards": mastered_cards,
        "learning_cards": learning_cards,
        "new_cards": new_cards,
        "due_today": due_today,
        "category_stats": dict(category_stats),
        "difficulty_distribution": difficulty_distribution,
        "average_ease_factor": round(average_ease_factor, 2),
        "mastery_rate": round(mastered_cards / total_cards * 100, 1) if total_cards > 0 else 0,
    }


# ============ UI表示 ============


def render_statistics_ui(stats: dict[str, Any], st_module: Any) -> None:
    """Streamlit UIで統計を表示"""
    st = st_module

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
                _render_category_chart(st, cat_name, cat_data)


def _render_category_chart(st_module: Any, category: str, data: dict[str, Any]) -> None:
    """個別のカテゴリエリアを描画"""
    st = st_module
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
