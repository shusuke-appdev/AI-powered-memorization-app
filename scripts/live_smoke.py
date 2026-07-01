"""Supabase本番相当接続でサービス層の最小スモークテストを実行する."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_SMOKE_ASSIGNMENT_DATE = "2099-12-31"


def _load_local_secrets() -> None:
    """Streamlit secretsを環境変数へ反映する。値は出力しない。"""
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists():
        return
    secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    if "SUPABASE_URL" in secrets:
        os.environ["SUPABASE_URL"] = secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in secrets:
        os.environ["SUPABASE_KEY"] = secrets["SUPABASE_KEY"]


def main() -> None:
    """ログイン相当、カード作成、復習更新、日次割当、削除を確認する。"""
    _load_local_secrets()
    from auth import (
        MAINTENANCE_USERNAME,
        create_session,
        delete_session,
        get_or_create_maintenance_user,
        login_user_direct,
    )
    from services.review_service import calculate_next_review
    from storage import (
        add_card,
        add_source_card,
        delete_cards_batch,
        delete_source_card,
        load_cards,
        load_daily_assignments,
        load_source_cards,
        mark_daily_assignment_complete,
        save_daily_assignments,
        update_card_progress,
    )

    maintenance_user = get_or_create_maintenance_user()
    user_id = maintenance_user["id"]
    success, message, login_user_id = login_user_direct(user_id)
    if not success or login_user_id != user_id:
        raise RuntimeError(f"ログイン相当の確認に失敗しました: {message}")

    token = create_session(user_id)
    if not token:
        raise RuntimeError("セッショントークンを作成できませんでした。")
    delete_session(token)

    source_id: str | None = None
    card_id: str | None = None
    try:
        source_id = add_source_card(
            user_id,
            "__codex_smoke_source__",
            title="__codex_smoke__",
            category="その他",
            card_type="知識",
        )
        if not source_id:
            raise RuntimeError("原文カードを作成できませんでした。")

        card_id = add_card(
            user_id,
            "__codex_smoke_question__",
            "",
            title="__codex_smoke__",
            category="その他",
            source_id=source_id,
            blank_count=0,
            card_type="知識",
            rank="B",
            highlighted_keywords="codex",
        )
        if not card_id:
            raise RuntimeError("暗記カードを作成できませんでした。")

        cards = load_cards(user_id)
        source_cards = load_source_cards(user_id)
        card = next(c for c in cards if str(c["id"]) == str(card_id))
        if not any(str(s["id"]) == str(source_id) for s in source_cards):
            raise RuntimeError("作成した原文カードを読み取れませんでした。")

        update_card_progress(user_id, card_id, calculate_next_review(4, card))
        saved = save_daily_assignments(
            user_id,
            _SMOKE_ASSIGNMENT_DATE,
            [str(card_id)],
            {str(card_id): card},
        )
        if not saved:
            raise RuntimeError("日次割当を保存できませんでした。")

        assignments = load_daily_assignments(user_id, _SMOKE_ASSIGNMENT_DATE)
        if len(assignments) != 1 or str(assignments[0]["card_id"]) != str(card_id):
            raise RuntimeError("日次割当を読み取れませんでした。")

        marked = mark_daily_assignment_complete(
            user_id,
            _SMOKE_ASSIGNMENT_DATE,
            str(card_id),
            quality=4,
        )
        if not marked:
            raise RuntimeError("日次割当を完了済みに更新できませんでした。")

        assignments = load_daily_assignments(user_id, _SMOKE_ASSIGNMENT_DATE)
        if not assignments[0]["completed_at"]:
            raise RuntimeError("日次割当の完了状態が保存されていません。")

        print(
            "LIVE_SMOKE_OK: login/session/card/source/progress/"
            f"daily_assignment/delete path verified with {MAINTENANCE_USERNAME}"
        )
    finally:
        if card_id:
            delete_cards_batch(user_id, [str(card_id)])
        if source_id:
            delete_source_card(user_id, str(source_id))


if __name__ == "__main__":
    main()
