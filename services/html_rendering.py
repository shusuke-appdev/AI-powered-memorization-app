"""HTML描画用の安全化ヘルパー."""

from __future__ import annotations

from html import escape

from config import CATEGORIES


def escape_html(value: object) -> str:
    """ユーザー入力をHTMLテキストとして安全に描画できる文字列へ変換."""
    return escape("" if value is None else str(value), quote=True)


def safe_category_class(category: object) -> str:
    """CSSクラスに使うカテゴリ名を既知カテゴリへ正規化."""
    category_text = "" if category is None else str(category)
    if category_text in CATEGORIES:
        return category_text
    return "その他"
