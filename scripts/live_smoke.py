"""Supabase本番相当接続でサービス層の最小スモークテストを実行する。"""

from __future__ import annotations

import os
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

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
    """ログイン、トランザクション保存、復習冪等性、削除を確認する。"""
    _load_local_secrets()
    from application_errors import PersistenceError
    from auth import (
        MAINTENANCE_USERNAME,
        create_session,
        delete_session,
        get_or_create_maintenance_user,
        login_user_direct,
    )
    from storage import (
        import_backup_atomic_rpc,
        load_cards,
        load_daily_assignments,
        load_source_cards,
        sync_daily_assignments,
    )
    from use_cases.card_workflows import (
        delete_source_bundle,
        save_source_with_cards,
    )
    from use_cases.review_workflows import complete_review

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
    try:
        rollback_title = "__codex_rollback__"
        try:
            import_backup_atomic_rpc(
                user_id,
                source_cards=[
                    {
                        "export_id": "rollback-source",
                        "source_text": "ロールバック確認用原文",
                        "title": rollback_title,
                        "category": "民法",
                        "card_type": "規範",
                    }
                ],
                cards=[
                    {
                        "source_export_id": "missing-source",
                        "question": "ロールバック確認用問題",
                        "answer": "確認用解答",
                        "title": rollback_title,
                        "category": "民法",
                        "card_type": "規範",
                        "rank": "B",
                        "blank_count": 1,
                    }
                ],
                reset_progress=False,
            )
        except PersistenceError:
            pass
        else:
            raise RuntimeError("不正インポートが成功扱いになりました。")

        rollback_residue = [
            source
            for source in load_source_cards(user_id)
            if source.get("title") == rollback_title
        ]
        if rollback_residue:
            for source in rollback_residue:
                delete_source_bundle(user_id, str(source["id"]))
            raise RuntimeError("失敗したインポートの原文が残りました。")

        result = save_source_with_cards(
            user_id,
            source_text="__codex_smoke_source__",
            title="__codex_smoke__",
            category="その他",
            card_type="知識",
            cards=[
                {
                    "question": "__codex_smoke_question__",
                    "answer": "",
                    "title": "__codex_smoke__",
                    "category": "その他",
                    "blank_count": 0,
                    "card_type": "知識",
                    "rank": "B",
                    "highlighted_keywords": "codex",
                }
            ],
        )
        if result.source_count != 1 or result.card_count != 1:
            raise RuntimeError("原文とカードを一括作成できませんでした。")
        source_id = result.source_id
        if not source_id:
            raise RuntimeError("作成した原文カードIDを取得できませんでした。")

        cards = load_cards(user_id)
        source_cards = load_source_cards(user_id)
        if not any(str(s["id"]) == source_id for s in source_cards):
            raise RuntimeError("作成した原文カードを読み取れませんでした。")
        card = next(
            c
            for c in cards
            if str(c.get("source_id")) == source_id
            and c.get("title") == "__codex_smoke__"
        )
        card_id = str(card["id"])

        synced = sync_daily_assignments(user_id, _SMOKE_ASSIGNMENT_DATE, [card_id])
        if len(synced) != 1:
            raise RuntimeError("日次割当を同期できませんでした。")

        assignments = load_daily_assignments(user_id, _SMOKE_ASSIGNMENT_DATE)
        if len(assignments) != 1 or str(assignments[0]["card_id"]) != card_id:
            raise RuntimeError("日次割当を読み取れませんでした。")

        start_barrier = Barrier(3)

        def submit_review():
            start_barrier.wait()
            return complete_review(user_id, _SMOKE_ASSIGNMENT_DATE, card, quality=4)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(submit_review) for _ in range(2)]
            start_barrier.wait()
            outcomes = [future.result() for future in futures]

        statuses = sorted(outcome.status for outcome in outcomes)
        if statuses != ["already_completed", "applied"]:
            raise RuntimeError("同時復習送信が原子的・冪等に処理されませんでした。")
        if not all(outcome.assignment_persisted for outcome in outcomes):
            raise RuntimeError("日次割当を完了済みに更新できませんでした。")

        assignments = load_daily_assignments(user_id, _SMOKE_ASSIGNMENT_DATE)
        if not assignments[0]["completed_at"]:
            raise RuntimeError("日次割当の完了状態が保存されていません。")

        print(
            "LIVE_SMOKE_OK: login/session/transactional-card/concurrent-review/"
            "review-idempotency/import-rollback/"
            f"daily-assignment/delete verified with {MAINTENANCE_USERNAME}"
        )
    finally:
        if source_id:
            delete_source_bundle(user_id, source_id)


if __name__ == "__main__":
    main()
