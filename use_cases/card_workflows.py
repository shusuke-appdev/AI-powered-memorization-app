"""カード作成・再生成・インポートの書き込みワークフロー."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from storage import (
    add_card,
    add_source_card,
    delete_card,
    delete_cards_batch,
    delete_source_card,
    update_source_card,
)


@dataclass(frozen=True)
class CardWorkflowResult:
    """複数カード書き込みの結果."""

    source_count: int
    card_count: int
    skipped_count: int = 0


def save_source_with_cards(
    user_id: str,
    *,
    source_text: str,
    title: str,
    category: str,
    card_type: str | None,
    cards: list[dict[str, Any]],
) -> CardWorkflowResult:
    """原文カードと暗記カードをまとめて保存し、途中失敗時は作成分を戻す."""
    source_id: str | None = None
    created_card_ids: list[str] = []
    try:
        source_id = add_source_card(
            user_id,
            source_text,
            title=title,
            category=category,
            card_type=card_type,
        )
        if not source_id:
            raise RuntimeError("原文カードの保存に失敗しました。")

        for card in cards:
            card_id = _add_card_from_payload(user_id, card, source_id=source_id)
            if not card_id:
                raise RuntimeError("暗記カードの保存に失敗しました。")
            created_card_ids.append(card_id)

    except Exception:
        _rollback_created_cards(user_id, created_card_ids)
        if source_id:
            delete_source_card(user_id, source_id)
        raise

    return CardWorkflowResult(source_count=1, card_count=len(created_card_ids))


def replace_source_cards(
    user_id: str,
    *,
    source_id: str,
    source_text: str,
    title: str,
    category: str,
    card_type: str | None,
    old_card_ids: list[str],
    cards: list[dict[str, Any]],
) -> CardWorkflowResult:
    """
    原文に紐づく暗記カードを置き換える。

    先に新カードを作成し、成功後に原文更新と旧カード削除を行うことで、
    カード生成や保存の途中失敗で既存データを失わないようにする。
    """
    created_card_ids: list[str] = []
    try:
        for card in cards:
            card_id = _add_card_from_payload(user_id, card, source_id=source_id)
            if not card_id:
                raise RuntimeError("再生成カードの保存に失敗しました。")
            created_card_ids.append(card_id)

        update_source_card(
            user_id,
            source_id,
            source_text=source_text,
            title=title,
            category=category,
            card_type=card_type,
        )
        delete_cards_batch(user_id, old_card_ids)

    except Exception:
        _rollback_created_cards(user_id, created_card_ids)
        raise

    return CardWorkflowResult(source_count=1, card_count=len(created_card_ids))


def import_backup_payload(
    user_id: str, import_result: dict[str, Any]
) -> CardWorkflowResult:
    """JSON/CSVインポート結果をDBへ保存し、JSONでは原文紐づきを復元する."""
    source_id_map: dict[str, str] = {}
    created_source_ids: list[str] = []
    created_card_ids: list[str] = []

    try:
        for source in import_result.get("source_cards", []):
            source_id = add_source_card(
                user_id,
                source.get("source_text", ""),
                title=source.get("title", ""),
                category=source.get("category", "その他"),
                card_type=source.get("card_type"),
            )
            if not source_id:
                raise RuntimeError("原文カードのインポートに失敗しました。")
            created_source_ids.append(source_id)
            export_id = source.get("export_id")
            if export_id:
                source_id_map[str(export_id)] = source_id

        for card in import_result.get("cards", []):
            source_id = source_id_map.get(str(card.get("source_export_id", "")))
            card_id = _add_card_from_payload(user_id, card, source_id=source_id)
            if not card_id:
                raise RuntimeError("暗記カードのインポートに失敗しました。")
            created_card_ids.append(card_id)

    except Exception:
        _rollback_created_cards(user_id, created_card_ids)
        for source_id in reversed(created_source_ids):
            delete_source_card(user_id, source_id)
        raise

    return CardWorkflowResult(
        source_count=len(created_source_ids),
        card_count=len(created_card_ids),
        skipped_count=int(import_result.get("skipped", 0)),
    )


def _add_card_from_payload(
    user_id: str,
    card: dict[str, Any],
    *,
    source_id: str | None,
) -> str | None:
    """インポート/生成カードpayloadからstorage.add_cardを呼ぶ."""
    return add_card(
        user_id,
        card.get("question", ""),
        card.get("answer", ""),
        title=card.get("title", ""),
        category=card.get("category", "その他"),
        source_id=source_id,
        blank_count=int(card.get("blank_count", 1)),
        card_type=card.get("card_type"),
        rank=card.get("rank", "B"),
        highlighted_keywords=card.get("highlighted_keywords", ""),
        ease_factor=card.get("ease_factor"),
        interval=card.get("interval"),
        repetitions=card.get("repetitions"),
        next_review=card.get("next_review"),
        is_favorite=bool(card.get("is_favorite", False)),
    )


def _rollback_created_cards(user_id: str, card_ids: list[str]) -> None:
    """作成済みカードをベストエフォートで削除する."""
    for card_id in reversed(card_ids):
        delete_card(user_id, card_id)
