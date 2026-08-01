"""カード作成・更新・再生成・インポートのトランザクション境界。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application_errors import ValidationError
from storage import (
    delete_source_bundle_rpc,
    import_backup_atomic_rpc,
    save_source_bundle_rpc,
)
from use_cases.card_models import CardDraft, SourceBundleCommand


@dataclass(frozen=True)
class CardWorkflowResult:
    """複数カード書き込みの結果。"""

    source_count: int
    card_count: int
    skipped_count: int = 0
    source_id: str | None = None


def save_source_with_cards(
    user_id: str,
    *,
    source_text: str,
    title: str,
    category: str,
    card_type: str | None,
    cards: list[dict[str, Any]],
) -> CardWorkflowResult:
    """原文カードと暗記カードを同一トランザクションで作成する。"""
    command = _build_command(
        "create",
        user_id,
        source_id=None,
        source_text=source_text,
        title=title,
        category=category,
        card_type=card_type,
        cards=cards,
    )
    return _save_bundle(command)


def update_source_with_cards(
    user_id: str,
    *,
    source_id: str,
    source_text: str,
    title: str,
    category: str,
    card_type: str,
    cards: list[dict[str, Any]],
) -> CardWorkflowResult:
    """原文と既存カードの変更を同一トランザクションで保存する。"""
    return _save_bundle(
        _build_command(
            "update",
            user_id,
            source_id=source_id,
            source_text=source_text,
            title=title,
            category=category,
            card_type=card_type,
            cards=cards,
        )
    )


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
    """原文と紐づきカード一式を同一トランザクションで置き換える。"""
    del old_card_ids  # DB側で対象source_idの所有カードを確定する。
    return _save_bundle(
        _build_command(
            "replace",
            user_id,
            source_id=source_id,
            source_text=source_text,
            title=title,
            category=category,
            card_type=card_type,
            cards=cards,
        )
    )


def delete_source_bundle(user_id: str, source_id: str) -> None:
    """原文カードと紐づきカードを一括削除する。"""
    delete_source_bundle_rpc(user_id, source_id)


def import_backup_payload(
    user_id: str, import_result: dict[str, Any]
) -> CardWorkflowResult:
    """検証済みバックアップを同一トランザクションで保存する。"""
    if import_result.get("error"):
        raise ValidationError(str(import_result["error"]))
    errors = import_result.get("errors") or []
    if errors:
        raise ValidationError(str(errors[0]))

    result = import_backup_atomic_rpc(
        user_id,
        source_cards=list(import_result.get("source_cards") or []),
        cards=list(import_result.get("cards") or []),
        reset_progress=bool(import_result.get("reset_progress", False)),
    )
    return CardWorkflowResult(
        source_count=int(result.get("source_count", 0)),
        card_count=int(result.get("card_count", 0)),
        skipped_count=int(import_result.get("skipped", 0)),
    )


def _build_command(
    mode: str,
    user_id: str,
    *,
    source_id: str | None,
    source_text: str,
    title: str,
    category: str,
    card_type: str | None,
    cards: list[dict[str, Any]],
) -> SourceBundleCommand:
    type_value = str(card_type or "")
    defaults = {
        "title": title,
        "category": category,
        "card_type": type_value,
        "rank": "B",
    }
    drafts = tuple(CardDraft.from_mapping(card, defaults=defaults) for card in cards)
    command = SourceBundleCommand(
        mode=mode,  # type: ignore[arg-type]
        user_id=user_id,
        source_id=source_id,
        source_text=source_text,
        title=title,
        category=category,
        card_type=type_value,
        cards=drafts,
    )
    command.validate()
    return command


def _save_bundle(command: SourceBundleCommand) -> CardWorkflowResult:
    result = save_source_bundle_rpc(command.user_id, command.to_rpc_payload())
    return CardWorkflowResult(
        source_count=int(result.get("source_count", 0)),
        card_count=int(result.get("card_count", 0)),
        source_id=str(result["source_id"]) if result.get("source_id") else None,
    )
