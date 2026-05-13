"""
ストレージモジュール - Supabase版（キャッシュ最適化）
ユーザー別のカードデータ管理
"""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from database import get_supabase
from services.review_service import get_initial_card_state

# キャッシュのTTL（秒）
_CACHE_TTL: int = 60


# ============ DTO変換 ============


def _row_to_card(row: dict[str, Any]) -> dict[str, Any]:
    """DBの行データをアプリ内カード形式に変換"""
    return {
        "id": row["id"],
        "question": row["question"],
        "answer": row["answer"],
        "title": row.get("title", ""),
        "category": row.get("category", "その他"),
        "ease_factor": row.get("ease_factor", 2.5),
        "interval": row.get("interval", 1),
        "repetitions": row.get("repetitions", 0),
        "next_review": row.get("next_review", date.today().isoformat()),
        "source_id": row.get("source_id"),
        "blank_count": row.get("blank_count", 1),
        "is_favorite": row.get("is_favorite", False),
        "card_type": row.get("card_type"),
        "rank": row.get("rank", "B"),
        "highlighted_keywords": row.get("highlighted_keywords", ""),
    }


# ============ 暗記カード管理 ============


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def _load_cards_cached(user_id: str) -> list[dict[str, Any]]:
    """キャッシュ付きでカードを読み込む（内部用）"""
    supabase = get_supabase()
    result = supabase.table("cards").select("*").eq("user_id", user_id).execute()

    if not result.data:
        return []

    return [_row_to_card(row) for row in result.data]


def load_cards(user_id: str) -> list[dict[str, Any]]:
    """指定ユーザーのカードを読み込む"""
    return _load_cards_cached(user_id)


def clear_cards_cache(user_id: str | None = None) -> None:
    """カードのキャッシュをクリア"""
    _load_cards_cached.clear()


def add_card(
    user_id: str,
    question: str,
    answer: str,
    title: str = "",
    category: str = "その他",
    source_id: str | None = None,
    blank_count: int = 1,
    card_type: str | None = None,
    rank: str = "B",
    highlighted_keywords: str = "",
) -> str | None:
    """カードを追加"""
    supabase = get_supabase()
    initial_state = get_initial_card_state()

    card_data: dict[str, Any] = {
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "title": title,
        "category": category,
        "ease_factor": initial_state["ease_factor"],
        "interval": initial_state["interval"],
        "repetitions": initial_state["repetitions"],
        "next_review": initial_state["next_review"],
        "blank_count": blank_count,
        "card_type": card_type,
        "rank": rank,
        "highlighted_keywords": highlighted_keywords,
    }

    if source_id:
        card_data["source_id"] = source_id

    result = supabase.table("cards").insert(card_data).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)

    return result.data[0]["id"] if result.data else None


# ============ 原文カード管理 ============


def add_source_card(
    user_id: str,
    source_text: str,
    title: str = "",
    category: str = "その他",
    card_type: str | None = None,
) -> str | None:
    """原文カードを追加"""
    supabase = get_supabase()

    result = (
        supabase.table("source_cards")
        .insert(
            {
                "user_id": user_id,
                "source_text": source_text,
                "title": title,
                "category": category,
                "card_type": card_type,
            }
        )
        .execute()
    )

    # キャッシュをクリア
    clear_source_cards_cache(user_id)

    if result.data:
        return result.data[0]["id"]
    return None


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def _load_source_cards_cached(user_id: str) -> list[dict[str, Any]]:
    """キャッシュ付きで原文カードを読み込む（内部用）"""
    supabase = get_supabase()
    result = supabase.table("source_cards").select("*").eq("user_id", user_id).execute()

    if not result.data:
        return []

    return result.data


def load_source_cards(user_id: str) -> list[dict[str, Any]]:
    """原文カードを読み込む"""
    return _load_source_cards_cached(user_id)


def clear_source_cards_cache(user_id: str | None = None) -> None:
    """原文カードのキャッシュをクリア"""
    _load_source_cards_cached.clear()


def get_source_card(source_id: str) -> dict[str, Any] | None:
    """特定の原文カードを取得"""
    supabase = get_supabase()
    result = supabase.table("source_cards").select("*").eq("id", source_id).execute()

    if result.data:
        return result.data[0]
    return None


def get_source_cards_by_ids(source_ids: list[str]) -> list[dict[str, Any]]:
    """複数の原文カードを取得"""
    if not source_ids:
        return []

    supabase = get_supabase()
    result = supabase.table("source_cards").select("*").in_("id", source_ids).execute()

    return result.data if result.data else []


def delete_source_card(user_id: str, source_id: str) -> None:
    """原文カードを削除"""
    supabase = get_supabase()

    supabase.table("source_cards").delete().eq("id", source_id).eq(
        "user_id", user_id
    ).execute()

    # キャッシュをクリア
    clear_source_cards_cache(user_id)


def update_source_card(
    user_id: str,
    source_id: str,
    source_text: str | None = None,
    title: str | None = None,
    category: str | None = None,
    card_type: str | None = None,
) -> None:
    """原文カードの内容を更新"""
    supabase = get_supabase()

    update_data: dict[str, Any] = {}
    if source_text is not None:
        update_data["source_text"] = source_text
    if title is not None:
        update_data["title"] = title
    if category is not None:
        update_data["category"] = category
    if card_type is not None:
        update_data["card_type"] = card_type

    if not update_data:
        return

    supabase.table("source_cards").update(update_data).eq("id", source_id).eq(
        "user_id", user_id
    ).execute()

    # キャッシュをクリア
    clear_source_cards_cache(user_id)


# ============ カード更新 ============


def update_card_progress(user_id: str, card_id: str, stats: dict[str, Any]) -> None:
    """カードの学習進捗を更新"""
    supabase = get_supabase()

    supabase.table("cards").update(
        {
            "ease_factor": stats["ease_factor"],
            "interval": stats["interval"],
            "repetitions": stats["repetitions"],
            "next_review": stats["next_review"],
        }
    ).eq("id", card_id).eq("user_id", user_id).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def update_card_content(
    user_id: str,
    card_id: str,
    question: str,
    answer: str,
    title: str = "",
    category: str = "その他",
    card_type: str | None = None,
    rank: str | None = None,
    highlighted_keywords: str | None = None,
) -> None:
    """カードの内容を更新"""
    supabase = get_supabase()

    update_data: dict[str, Any] = {
        "question": question,
        "answer": answer,
        "title": title,
        "category": category,
    }
    if card_type is not None:
        update_data["card_type"] = card_type
    if rank is not None:
        update_data["rank"] = rank
    if highlighted_keywords is not None:
        update_data["highlighted_keywords"] = highlighted_keywords

    supabase.table("cards").update(update_data).eq("id", card_id).eq(
        "user_id", user_id
    ).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def delete_card(user_id: str, card_id: str) -> None:
    """カードを削除"""
    supabase = get_supabase()

    supabase.table("cards").delete().eq("id", card_id).eq("user_id", user_id).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def delete_cards_batch(user_id: str, card_ids: list[str]) -> None:
    """複数のカードを一括削除"""
    if not card_ids:
        return

    supabase = get_supabase()

    # in_演算子で一括削除（パフォーマンス最適化）
    supabase.table("cards").delete().in_("id", card_ids).eq(
        "user_id", user_id
    ).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def toggle_favorite(user_id: str, card_id: str, is_favorite: bool) -> None:
    """カードのお気に入り状態をトグル"""
    supabase = get_supabase()

    supabase.table("cards").update({"is_favorite": is_favorite}).eq("id", card_id).eq(
        "user_id", user_id
    ).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def toggle_favorite_by_source_id(
    user_id: str, source_id: str, is_favorite: bool
) -> None:
    """原文IDに紐づく全てのカードのお気に入り状態をトグル"""
    supabase = get_supabase()

    supabase.table("cards").update({"is_favorite": is_favorite}).eq(
        "source_id", source_id
    ).eq("user_id", user_id).execute()

    # キャッシュをクリア
    clear_cards_cache(user_id)


def get_favorite_cards(user_id: str) -> list[dict[str, Any]]:
    """お気に入りカードのみを取得"""
    cards = load_cards(user_id)
    return [c for c in cards if c.get("is_favorite", False)]
