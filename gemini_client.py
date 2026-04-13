"""
gemini_client.py — 後方互換ラッパー

ロジック本体は services/ai_service.py と services/card_service.py に移行済み。
既存のインポートを壊さないための薄いラッパー。
"""

from __future__ import annotations

# 後方互換のため re-export
from services.ai_service import (  # noqa: F401
    help_chat,
    simple_split,
    split_into_phrases,
    suggest_blanks,
)
from services.card_service import (  # noqa: F401
    generate_cards_from_selection,
    generate_flashcards,
    parse_blanks_from_text,
    validate_blank_markers,
)
