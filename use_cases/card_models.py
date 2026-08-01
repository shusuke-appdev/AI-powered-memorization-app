"""カード書き込み境界の検証済みコマンド型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from application_errors import ValidationError
from config import BLANK_DISABLED_TYPES, CARD_TYPES, CATEGORIES, RANKS

BundleMode = Literal["create", "update", "replace"]


@dataclass(frozen=True)
class CardDraft:
    question: str
    answer: str
    title: str
    category: str
    card_type: str
    rank: str
    blank_count: int
    highlighted_keywords: str = ""
    card_id: str | None = None
    ease_factor: float | None = None
    interval: int | None = None
    repetitions: int | None = None
    next_review: str | None = None
    is_favorite: bool = False
    source_export_id: str = ""

    @classmethod
    def from_mapping(
        cls,
        value: dict[str, Any],
        *,
        defaults: dict[str, Any] | None = None,
    ) -> CardDraft:
        merged = {**(defaults or {}), **value}
        try:
            draft = cls(
                question=str(merged.get("question") or "").strip(),
                answer=str(merged.get("answer") or "").strip(),
                title=str(merged.get("title") or "").strip(),
                category=str(merged.get("category") or "").strip(),
                card_type=str(merged.get("card_type") or "").strip(),
                rank=str(merged.get("rank") or "").strip(),
                blank_count=int(merged.get("blank_count", 0)),
                highlighted_keywords=str(
                    merged.get("highlighted_keywords") or ""
                ).strip(),
                card_id=_optional_text(merged.get("id") or merged.get("card_id")),
                ease_factor=_optional_float(merged.get("ease_factor")),
                interval=_optional_int(merged.get("interval")),
                repetitions=_optional_int(merged.get("repetitions")),
                next_review=_optional_text(merged.get("next_review")),
                is_favorite=bool(merged.get("is_favorite", False)),
                source_export_id=str(merged.get("source_export_id") or ""),
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("カードの数値項目が不正です。") from exc
        draft.validate()
        return draft

    def validate(self) -> None:
        if not self.question:
            raise ValidationError("問題または本文を入力してください。")
        if self.category not in CATEGORIES:
            raise ValidationError("カテゴリを選択してください。")
        if self.card_type not in CARD_TYPES:
            raise ValidationError("カードタイプを選択してください。")
        if self.rank not in RANKS:
            raise ValidationError("重要度ランクが不正です。")
        if self.card_type in BLANK_DISABLED_TYPES:
            if self.answer:
                raise ValidationError(
                    "知識・類型カードには穴埋め解答を保存できません。"
                )
            if self.blank_count != 0:
                raise ValidationError(
                    "知識・類型カードの穴埋め数は0である必要があります。"
                )
        else:
            if not self.answer:
                raise ValidationError("規範・判例カードには答えが必要です。")
            if self.blank_count < 1:
                raise ValidationError("穴埋めカードには1箇所以上の穴埋めが必要です。")
        if self.ease_factor is not None and self.ease_factor < 1.3:
            raise ValidationError("ease factorは1.3以上である必要があります。")
        for value in (self.interval, self.repetitions):
            if value is not None and value < 0:
                raise ValidationError("学習進捗に負の値は指定できません。")

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("card_id")
        payload.pop("source_export_id")
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class SourceBundleCommand:
    mode: BundleMode
    user_id: str
    source_id: str | None
    source_text: str
    title: str
    category: str
    card_type: str
    cards: tuple[CardDraft, ...]

    def validate(self) -> None:
        if self.mode not in ("create", "update", "replace"):
            raise ValidationError("未対応の保存モードです。")
        if not self.user_id:
            raise ValidationError("ユーザー情報がありません。")
        if self.mode != "create" and not self.source_id:
            raise ValidationError("更新対象の原文カードがありません。")
        if not self.source_text.strip():
            raise ValidationError("原文を入力してください。")
        if self.category not in CATEGORIES:
            raise ValidationError("カテゴリを選択してください。")
        if self.card_type not in CARD_TYPES:
            raise ValidationError("カードタイプを選択してください。")
        if not self.cards:
            raise ValidationError("保存できるカードがありません。")
        for card in self.cards:
            card.validate()
            if card.category != self.category or card.card_type != self.card_type:
                raise ValidationError("原文とカードのカテゴリ・タイプが一致しません。")

    def to_rpc_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "mode": self.mode,
            "source_id": self.source_id,
            "source_text": self.source_text.strip(),
            "title": self.title.strip(),
            "category": self.category,
            "card_type": self.card_type,
            "cards": [{**card.to_payload(), "id": card.card_id} for card in self.cards],
        }


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: object) -> int | None:
    return None if value in (None, "") else int(value)


def _optional_float(value: object) -> float | None:
    return None if value in (None, "") else float(value)
