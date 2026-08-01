"""秘密値とセッショントークンを除外した移行前論理バックアップを作成する。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_local_secrets() -> None:
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists():
        return
    secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    for key in ("SUPABASE_URL", "SUPABASE_KEY"):
        if key in secrets:
            os.environ[key] = secrets[key]


def main() -> None:
    """全ユーザーのカード本文と進捗をローカルJSONへ保存する。"""
    _load_local_secrets()
    from database import get_supabase
    from export_import import export_cards_json
    from storage import load_cards, load_source_cards

    users_result = (
        get_supabase().table("users").select("id, username, daily_quota").execute()
    )
    users = users_result.data or []
    payload = {
        "format": "memorization-app-logical-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "users": [],
    }
    card_count = 0
    source_count = 0
    for user in users:
        user_id = str(user["id"])
        cards = load_cards(user_id)
        source_cards = load_source_cards(user_id)
        card_count += len(cards)
        source_count += len(source_cards)
        payload["users"].append(
            {
                "id": user_id,
                "username": str(user.get("username") or ""),
                "daily_quota": user.get("daily_quota"),
                "backup": json.loads(export_cards_json(cards, source_cards)),
            }
        )

    output_dir = Path(".states")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"pre_migration_backup_{timestamp}.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    output_path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    print(
        f"BACKUP_OK path={output_path} users={len(users)} "
        f"sources={source_count} cards={card_count} sha256={digest}"
    )


if __name__ == "__main__":
    main()
