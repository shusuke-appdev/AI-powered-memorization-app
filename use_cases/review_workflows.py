"""復習完了の永続化と互換フォールバック。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from application_errors import MigrationUnavailableError
from services.review_service import calculate_next_review
from storage import complete_daily_review_atomic, update_card_progress


@dataclass(frozen=True)
class ReviewOutcome:
    status: Literal["applied", "already_completed"]
    assignment_persisted: bool
    progress: dict[str, Any]


def complete_review(
    user_id: str,
    assignment_date: str,
    card: dict[str, Any],
    *,
    quality: int,
) -> ReviewOutcome:
    """DB成功後にだけ呼び出し元が画面状態を進められる結果を返す。"""
    progress = calculate_next_review(quality, card)
    try:
        result = complete_daily_review_atomic(
            user_id,
            assignment_date,
            str(card["id"]),
            quality=quality,
            stats=progress,
        )
    except MigrationUnavailableError:
        update_card_progress(user_id, str(card["id"]), progress)
        return ReviewOutcome(
            status="applied",
            assignment_persisted=False,
            progress=progress,
        )

    status = str(result.get("status", "applied"))
    return ReviewOutcome(
        status="already_completed" if status == "already_completed" else "applied",
        assignment_persisted=True,
        progress=progress,
    )
