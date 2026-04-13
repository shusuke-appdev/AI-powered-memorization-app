"""
utils.py — 後方互換ラッパー

ロジック本体は services/review_service.py に移行済み。
既存のインポートを壊さないための薄いラッパー。
"""

from __future__ import annotations

# 後方互換のため re-export
from config import (  # noqa: F401
    CATEGORY_COLORS,
    CATEGORY_GROUPS,
    get_all_category_css,
    get_category_colors,
    get_category_group,
)
from services.review_service import (  # noqa: F401
    calculate_next_review,
    get_initial_card_state,
    select_hybrid_quota,
)
