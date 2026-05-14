"""
アプリケーション設定・定数の一元管理モジュール
"""

from __future__ import annotations

# ============ カテゴリ定数 ============

CATEGORIES: list[str] = [
    "民法",
    "商法",
    "刑法",
    "憲法",
    "行政法",
    "民事訴訟法",
    "刑事訴訟法",
    "その他",
]

# カテゴリ分類（科目 → グループ）
CATEGORY_GROUPS: dict[str, list[str]] = {
    "民事系": ["民法", "商法", "民事訴訟法"],
    "刑事系": ["刑法", "刑事訴訟法"],
    "公法系": ["憲法", "行政法"],
    "その他": ["その他"],
}

# カラーパレット（ライトモード / ダークモード）
CATEGORY_COLORS: dict[str, dict[str, dict[str, str]]] = {
    "民事系": {
        "light": {"bg": "#fecaca", "text": "#b91c1c", "border": "#fca5a5"},
        "dark": {"bg": "#7f1d1d", "text": "#fca5a5", "border": "#991b1b"},
    },
    "刑事系": {
        "light": {"bg": "#bfdbfe", "text": "#1d4ed8", "border": "#93c5fd"},
        "dark": {"bg": "#1e3a5f", "text": "#93c5fd", "border": "#1e40af"},
    },
    "公法系": {
        "light": {"bg": "#bbf7d0", "text": "#15803d", "border": "#86efac"},
        "dark": {"bg": "#14532d", "text": "#86efac", "border": "#166534"},
    },
    "その他": {
        "light": {"bg": "#fef08a", "text": "#a16207", "border": "#fde047"},
        "dark": {"bg": "#713f12", "text": "#fde047", "border": "#854d0e"},
    },
}

# ============ カードタイプ定数 ============

CARD_TYPES: list[str] = ["規範", "判例", "類型", "知識"]
BLANK_DISABLED_TYPES: list[str] = ["類型", "知識"]  # 穴埋めなしタイプ
RANKS: list[str] = ["A+", "A", "B+", "B", "C"]
RANK_WEIGHT: dict[str, int] = {"A+": 5, "A": 4, "B+": 3, "B": 2, "C": 1}


# ============ アルゴリズム定数 ============

BLANKS_PER_CARD: int = 5  # 1カードあたりの最大穴埋め箇所数
DEFAULT_EASE_FACTOR: float = 2.5
MIN_EASE_FACTOR: float = 1.3
MASTERY_THRESHOLD: int = 5  # 習得判定の連続正解回数


# ============ ヘルパー関数 ============


def get_category_group(category: str) -> str:
    """科目名からカテゴリグループを取得"""
    for group, subjects in CATEGORY_GROUPS.items():
        if category in subjects:
            return group
    return "その他"


def get_category_colors(category: str, *, is_dark_mode: bool = False) -> dict[str, str]:
    """
    カテゴリ名から色情報を取得

    Args:
        category: 科目名（例: "民法", "刑法"）
        is_dark_mode: ダークモードかどうか

    Returns:
        dict: {"bg": 背景色, "text": 文字色, "border": ボーダー色}
    """
    group = get_category_group(category)
    mode = "dark" if is_dark_mode else "light"
    return CATEGORY_COLORS.get(group, CATEGORY_COLORS["その他"])[mode]
