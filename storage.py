"""
ストレージモジュール - Supabase版（キャッシュ最適化）
ユーザー別のカードデータ管理
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st
from streamlit.runtime import exists as streamlit_runtime_exists

from application_errors import (
    MigrationUnavailableError,
    PersistenceError,
    RecordNotFoundError,
)
from database import get_supabase
from services.review_service import get_initial_card_state
from services.time_service import local_date_iso

# キャッシュのTTL（秒）
_CACHE_TTL: int = 60
_PAGE_SIZE: int = 1000
_SOURCE_ID_BATCH_SIZE: int = 100

_CARD_COLUMNS = (
    "id, question, answer, title, category, ease_factor, interval, repetitions, "
    "next_review, source_id, blank_count, is_favorite, card_type, rank, "
    "highlighted_keywords"
)
_SOURCE_CARD_COLUMNS = (
    "id, user_id, source_text, title, category, card_type, created_at"
)

_FunctionT = TypeVar("_FunctionT", bound=Callable[..., Any])


def _cache_data_when_streamlit_runs(function: _FunctionT) -> _FunctionT:
    """bare PythonスクリプトではStreamlitキャッシュと警告を発生させない。"""
    if streamlit_runtime_exists():
        return st.cache_data(ttl=_CACHE_TTL, show_spinner=False)(function)
    return function


def _clear_function_cache(function: Callable[..., Any]) -> None:
    clear = getattr(function, "clear", None)
    if callable(clear):
        clear()


# ============ DTO変換 ============


def _fetch_all_pages(
    fetch_page: Callable[[int, int], list[dict[str, Any]]],
    *,
    page_size: int = _PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Supabaseのrange上限に備えて全ページを結合する。"""
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + page_size - 1
        page = fetch_page(start, end)
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _row_to_card(row: dict[str, Any]) -> dict[str, Any]:
    """DBの行データをアプリ内カード形式に変換"""
    return {
        "id": row["id"],
        "question": row.get("question") or "",
        "answer": row.get("answer") or "",
        "title": row.get("title") or "",
        "category": row.get("category") or "その他",
        "ease_factor": row.get("ease_factor") or 2.5,
        "interval": row.get("interval") or 1,
        "repetitions": row.get("repetitions") or 0,
        "next_review": row.get("next_review") or local_date_iso(),
        "source_id": row.get("source_id"),
        "blank_count": row.get("blank_count") or 0,
        "is_favorite": bool(row.get("is_favorite", False)),
        "card_type": row.get("card_type"),
        "rank": row.get("rank") or "B",
        "highlighted_keywords": row.get("highlighted_keywords") or "",
    }


# ============ 暗記カード管理 ============


@_cache_data_when_streamlit_runs
def _load_cards_cached(user_id: str) -> list[dict[str, Any]]:
    """キャッシュ付きでカードを読み込む（内部用）"""
    supabase = get_supabase()

    def fetch_page(start: int, end: int) -> list[dict[str, Any]]:
        result = (
            supabase.table("cards")
            .select(_CARD_COLUMNS)
            .eq("user_id", user_id)
            .order("id")
            .range(start, end)
            .execute()
        )
        return result.data if result.data else []

    rows = _fetch_all_pages(fetch_page)
    if not rows:
        return []

    return [_row_to_card(row) for row in rows]


def load_cards(user_id: str) -> list[dict[str, Any]]:
    """指定ユーザーのカードを読み込む"""
    return _load_cards_cached(user_id)


def clear_cards_cache(user_id: str | None = None) -> None:
    """カードのキャッシュをクリア"""
    _clear_function_cache(_load_cards_cached)


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
    ease_factor: float | None = None,
    interval: int | None = None,
    repetitions: int | None = None,
    next_review: str | None = None,
    is_favorite: bool = False,
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
        "ease_factor": ease_factor
        if ease_factor is not None
        else initial_state["ease_factor"],
        "interval": interval if interval is not None else initial_state["interval"],
        "repetitions": repetitions
        if repetitions is not None
        else initial_state["repetitions"],
        "next_review": next_review or initial_state["next_review"],
        "blank_count": blank_count,
        "card_type": card_type,
        "rank": rank,
        "highlighted_keywords": highlighted_keywords,
        "is_favorite": is_favorite,
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


@_cache_data_when_streamlit_runs
def _load_source_cards_cached(user_id: str) -> list[dict[str, Any]]:
    """キャッシュ付きで原文カードを読み込む（内部用）"""
    supabase = get_supabase()

    def fetch_page(start: int, end: int) -> list[dict[str, Any]]:
        result = (
            supabase.table("source_cards")
            .select(_SOURCE_CARD_COLUMNS)
            .eq("user_id", user_id)
            .order("id")
            .range(start, end)
            .execute()
        )
        return result.data if result.data else []

    return _fetch_all_pages(fetch_page)


def load_source_cards(user_id: str) -> list[dict[str, Any]]:
    """原文カードを読み込む"""
    return _load_source_cards_cached(user_id)


def clear_source_cards_cache(user_id: str | None = None) -> None:
    """原文カードのキャッシュをクリア"""
    _clear_function_cache(_load_source_cards_cached)


def _require_affected_row(result: Any, label: str) -> None:
    """単一行更新が0件だった場合に成功扱いしない。"""
    if not getattr(result, "data", None):
        raise RecordNotFoundError(f"{label}が見つからないか、更新権限がありません。")


def get_source_card(user_id: str, source_id: str) -> dict[str, Any] | None:
    """特定の原文カードを取得"""
    supabase = get_supabase()
    result = (
        supabase.table("source_cards")
        .select("*")
        .eq("id", source_id)
        .eq("user_id", user_id)
        .execute()
    )

    if result.data:
        return result.data[0]
    return None


def get_source_cards_by_ids(
    user_id: str, source_ids: list[str]
) -> list[dict[str, Any]]:
    """複数の原文カードを取得"""
    if not source_ids:
        return []

    supabase = get_supabase()
    rows: list[dict[str, Any]] = []
    for start in range(0, len(source_ids), _SOURCE_ID_BATCH_SIZE):
        batch = source_ids[start : start + _SOURCE_ID_BATCH_SIZE]
        result = (
            supabase.table("source_cards")
            .select(_SOURCE_CARD_COLUMNS)
            .in_("id", batch)
            .eq("user_id", user_id)
            .execute()
        )
        if result.data:
            rows.extend(result.data)

    return rows


def delete_source_card(user_id: str, source_id: str) -> None:
    """原文カードを削除"""
    supabase = get_supabase()

    result = (
        supabase.table("source_cards")
        .delete()
        .eq("id", source_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "原文カード")

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

    result = (
        supabase.table("source_cards")
        .update(update_data)
        .eq("id", source_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "原文カード")

    # キャッシュをクリア
    clear_source_cards_cache(user_id)


# ============ カード更新 ============


def update_card_progress(user_id: str, card_id: str, stats: dict[str, Any]) -> None:
    """カードの学習進捗を更新"""
    supabase = get_supabase()

    result = (
        supabase.table("cards")
        .update(
            {
                "ease_factor": stats["ease_factor"],
                "interval": stats["interval"],
                "repetitions": stats["repetitions"],
                "next_review": stats["next_review"],
            }
        )
        .eq("id", card_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "カード")

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
    blank_count: int | None = None,
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
    if blank_count is not None:
        update_data["blank_count"] = blank_count

    result = (
        supabase.table("cards")
        .update(update_data)
        .eq("id", card_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "カード")

    # キャッシュをクリア
    clear_cards_cache(user_id)


def delete_card(user_id: str, card_id: str) -> None:
    """カードを削除"""
    supabase = get_supabase()

    result = (
        supabase.table("cards")
        .delete()
        .eq("id", card_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "カード")

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


# ============ 日次ノルマ割当 ============


def load_daily_assignments(user_id: str, assignment_date: str) -> list[dict[str, Any]]:
    """指定日のDB保存済みノルマ割当を取得する。"""
    supabase = get_supabase()
    try:
        result = (
            supabase.table("daily_assignments")
            .select("card_id, source_id, position, completed_at, quality")
            .eq("user_id", user_id)
            .eq("assignment_date", assignment_date)
            .order("position")
            .execute()
        )
    except Exception as exc:
        if _is_missing_daily_assignments_error(exc):
            return []
        raise
    return result.data if result.data else []


def save_daily_assignments(
    user_id: str,
    assignment_date: str,
    card_ids: list[str],
    cards_by_id: dict[str, dict[str, Any]],
) -> bool:
    """指定日のノルマ割当をDBへ保存する。テーブル未適用ならFalseを返す。"""
    try:
        sync_daily_assignments(user_id, assignment_date, card_ids)
    except MigrationUnavailableError:
        return False
    return True


def mark_daily_assignment_complete(
    user_id: str,
    assignment_date: str,
    card_id: str,
    *,
    quality: int,
) -> bool:
    """指定日のカード割当を完了済みにする。テーブル未適用ならFalseを返す。"""
    raise PersistenceError(
        "復習進捗はcomplete_daily_review_atomicから更新してください。"
    )


def sync_daily_assignments(
    user_id: str,
    assignment_date: str,
    card_ids: list[str],
) -> list[dict[str, Any]]:
    """当日割当を所有者検証・ロック付きRPCで同期する。"""
    supabase = get_supabase()
    try:
        result = supabase.rpc(
            "sync_daily_assignments",
            {
                "p_user_id": user_id,
                "p_assignment_date": assignment_date,
                "p_card_ids": card_ids,
            },
        ).execute()
    except Exception as exc:
        if _is_missing_database_object_error(exc, "sync_daily_assignments"):
            raise MigrationUnavailableError() from exc
        raise
    return _rpc_rows(result)


def complete_daily_review_atomic(
    user_id: str,
    assignment_date: str,
    card_id: str,
    *,
    quality: int,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """カード進捗と割当完了を単一トランザクションで更新する。"""
    supabase = get_supabase()
    try:
        result = supabase.rpc(
            "complete_daily_review",
            {
                "p_user_id": user_id,
                "p_assignment_date": assignment_date,
                "p_card_id": card_id,
                "p_quality": quality,
                "p_ease_factor": stats["ease_factor"],
                "p_interval": stats["interval"],
                "p_repetitions": stats["repetitions"],
                "p_next_review": stats["next_review"],
            },
        ).execute()
    except Exception as exc:
        if _is_missing_database_object_error(exc, "complete_daily_review"):
            raise MigrationUnavailableError() from exc
        raise
    rows = _rpc_rows(result)
    if not rows:
        raise PersistenceError("復習結果を保存できませんでした。")
    clear_cards_cache(user_id)
    return rows[0]


def save_source_bundle_rpc(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """原文とカードをトランザクションで作成・更新・置換する。"""
    try:
        result = (
            get_supabase()
            .rpc(
                "save_source_bundle",
                {"p_user_id": user_id, "p_bundle": payload},
            )
            .execute()
        )
    except Exception as exc:
        raise PersistenceError("カードを保存できませんでした。") from exc
    rows = _rpc_rows(result)
    if not rows:
        raise PersistenceError("カードを保存できませんでした。")
    clear_cards_cache(user_id)
    clear_source_cards_cache(user_id)
    return rows[0]


def delete_source_bundle_rpc(user_id: str, source_id: str) -> None:
    """原文と関連カードをトランザクションで削除する。"""
    try:
        result = (
            get_supabase()
            .rpc(
                "delete_source_bundle",
                {"p_user_id": user_id, "p_source_id": source_id},
            )
            .execute()
        )
    except Exception as exc:
        if str(getattr(exc, "code", "")) == "42501":
            raise RecordNotFoundError("削除対象の原文カードが見つかりません。") from exc
        raise PersistenceError("原文カードを削除できませんでした。") from exc
    rows = _rpc_rows(result)
    if not rows or int(rows[0].get("source_count", 0)) != 1:
        raise RecordNotFoundError("削除対象の原文カードが見つかりません。")
    clear_cards_cache(user_id)
    clear_source_cards_cache(user_id)


def import_backup_atomic_rpc(
    user_id: str,
    *,
    source_cards: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    reset_progress: bool,
) -> dict[str, Any]:
    """検証済みバックアップを単一トランザクションで保存する。"""
    try:
        result = (
            get_supabase()
            .rpc(
                "import_backup_atomic",
                {
                    "p_user_id": user_id,
                    "p_sources": source_cards,
                    "p_cards": cards,
                    "p_reset_progress": reset_progress,
                },
            )
            .execute()
        )
    except Exception as exc:
        raise PersistenceError("バックアップを保存できませんでした。") from exc
    rows = _rpc_rows(result)
    if not rows:
        raise PersistenceError("バックアップを保存できませんでした。")
    clear_cards_cache(user_id)
    clear_source_cards_cache(user_id)
    return rows[0]


def _rpc_rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _is_missing_database_object_error(exc: Exception, object_name: str) -> bool:
    message = str(exc).lower()
    code = str(getattr(exc, "code", "")).upper()
    return object_name.lower() in message and (
        code in {"42P01", "42883", "PGRST202"}
        or "does not exist" in message
        or "could not find" in message
        or "schema cache" in message
    )


def _is_missing_daily_assignments_error(exc: Exception) -> bool:
    """daily_assignments未適用時だけ互換フォールバックを許可する。"""
    message = str(exc).lower()
    return "daily_assignments" in message and (
        "does not exist" in message
        or "could not find" in message
        or "schema cache" in message
    )


def toggle_favorite(user_id: str, card_id: str, is_favorite: bool) -> None:
    """カードのお気に入り状態をトグル"""
    supabase = get_supabase()

    result = (
        supabase.table("cards")
        .update({"is_favorite": is_favorite})
        .eq("id", card_id)
        .eq("user_id", user_id)
        .select("id")
        .execute()
    )
    _require_affected_row(result, "カード")

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
