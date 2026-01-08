"""
統計モジュール - 学習統計の計算と表示
"""
import datetime
from collections import defaultdict

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
    category_stats = defaultdict(lambda: {"total": 0, "mastered": 0, "due": 0})
    for card in cards:
        category = card.get("category", "その他")
        category_stats[category]["total"] += 1
        if card.get("repetitions", 0) >= 5:
            category_stats[category]["mastered"] += 1
        if card.get("next_review", "") <= today:
            category_stats[category]["due"] += 1
    
    # 難易度分布（ease_factorベース）
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
    st.markdown("**難易度分布**")
    diff = stats["difficulty_distribution"]
    st.markdown(f"🟢 簡単: {diff['easy']} | 🟡 普通: {diff['medium']} | 🔴 難しい: {diff['hard']}")
    
    # カテゴリ別統計（折りたたみ）
    if stats["category_stats"]:
        with st.expander("📊 カテゴリ別統計", expanded=False):
            for category, cat_stats in stats["category_stats"].items():
                mastery = cat_stats["mastered"] / cat_stats["total"] * 100 if cat_stats["total"] > 0 else 0
                st.markdown(f"**{category}**: {cat_stats['total']}枚（習得{cat_stats['mastered']}枚, 復習待ち{cat_stats['due']}枚）")
