"""
統計モジュール - 学習統計の計算と表示
"""
import datetime
from collections import defaultdict
import plotly.express as px
import pandas as pd

def calculate_statistics(cards, source_cards=None):
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
        }
    
    today = datetime.date.today().isoformat()
    
    # 基本統計
    total_cards = len(cards)
    mastered_cards = sum(1 for c in cards if c.get("repetitions", 0) >= 5)
    learning_cards = sum(1 for c in cards if 0 < c.get("repetitions", 0) < 5)
    new_cards = sum(1 for c in cards if c.get("repetitions", 0) == 0)
    due_today = sum(1 for c in cards if c.get("next_review", "") <= today)
    
    # カテゴリ別統計
    # total, mastered, due, difficulty(easy/medium/hard)
    category_stats = defaultdict(lambda: {
        "total": 0, 
        "mastered": 0, 
        "due": 0, 
        "difficulty": {"easy": 0, "medium": 0, "hard": 0}
    })
    
    for card in cards:
        category = card.get("category", "その他")
        category_stats[category]["total"] += 1
        
        if card.get("repetitions", 0) >= 5:
            category_stats[category]["mastered"] += 1
        if card.get("next_review", "") <= today:
            category_stats[category]["due"] += 1
            
        # 難易度判定
        ef = card.get("ease_factor", 2.5)
        if ef >= 2.5:
            category_stats[category]["difficulty"]["easy"] += 1
        elif ef >= 2.0:
            category_stats[category]["difficulty"]["medium"] += 1
        else:
            category_stats[category]["difficulty"]["hard"] += 1
    
    # 全体の難易度分布（ease_factorベース）
    difficulty_distribution = {"easy": 0, "medium": 0, "hard": 0}
    total_ease = 0
    for card in cards:
        ef = card.get("ease_factor", 2.5)
        total_ease += ef
        if ef >= 2.5:
            difficulty_distribution["easy"] += 1
        elif ef >= 2.0:
            difficulty_distribution["medium"] += 1
        else:
            difficulty_distribution["hard"] += 1
    
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

def render_statistics_ui(stats, st_module):
    """
    Streamlit UIで統計を表示
    
    Args:
        stats: calculate_statistics()の戻り値
        st_module: streamlitモジュール
    """
    st = st_module
    
    # メトリクス行
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 総カード数", stats["total_cards"])
    with col2:
        st.metric("✅ 習得済み", stats["mastered_cards"])
    with col3:
        st.metric("📖 学習中", stats["learning_cards"])
    with col4:
        st.metric("📅 本日復習", stats["due_today"])
    
    # 習得率プログレスバー
    if stats["total_cards"] > 0:
        st.progress(stats["mastery_rate"] / 100, text=f"習得率: {stats['mastery_rate']}%")
    
    # 難易度分布（シンプルなテキスト表示）
    st.markdown("**全体の難易度分布**")
    diff = stats["difficulty_distribution"]
    st.markdown(f"🟢 簡単: {diff['easy']} | 🟡 普通: {diff['medium']} | 🔴 難しい: {diff['hard']}")
    
    st.markdown("---")
    
    # カテゴリ別統計（グラフ表示）
    if stats["category_stats"]:
        st.subheader("📊 カテゴリ別 達成状況")
        
        categories = list(stats["category_stats"].items())
        
        # 4列レイアウトで表示（gap=smallで間隔を狭く）
        cols = st.columns(4, gap="small")
        
        for idx, (cat_name, cat_data) in enumerate(categories):
            with cols[idx % 4]:
                render_category_chart(st, cat_name, cat_data)

def render_category_chart(st, category, data):
    """個別のカテゴリエリアを描画"""
    st.markdown(f"**{category}**")
    
    # 基本情報の表示
    total = data["total"]
    mastery = round(data["mastered"] / total * 100, 1) if total > 0 else 0
    st.caption(f"総数: {total}枚 | 習得率: {mastery}% | 復習待ち: {data['due']}枚")
    
    # 円グラフデータの作成
    diff_data = data["difficulty"]
    
    # データフレーム作成（凡例の順序制御のため）
    chart_df = pd.DataFrame([
        {"Status": "簡単", "Count": diff_data["easy"], "Color": "#10b981"},  # Green
        {"Status": "普通", "Count": diff_data["medium"], "Color": "#f59e0b"}, # Yellow/Orange
        {"Status": "難しい", "Count": diff_data["hard"], "Color": "#ef4444"}    # Red
    ])
    
    # カウントが0の項目を除外（グラフを綺麗にするため）
    chart_df = chart_df[chart_df["Count"] > 0]
    
    if not chart_df.empty:
        fig = px.pie(
            chart_df, 
            values="Count", 
            names="Status",
            color="Status",
            color_discrete_map={
                "簡単": "#10b981",
                "普通": "#f59e0b",
                "難しい": "#ef4444"
            },
            hole=0.4, # ドーナツチャートにする
        )
        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=200,
            showlegend=False,
            annotations=[dict(text=category, x=0.5, y=0.5, font_size=16, showarrow=False)]
        )
        fig.update_traces(textposition='inside', textinfo='percent')
        
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{category}")
    else:
        st.info("データがありません")

