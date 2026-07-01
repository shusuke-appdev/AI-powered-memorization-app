"""
認証モジュール - Supabase版
ユーザー登録、ログイン、セッション管理
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st

from database import get_supabase

SESSION_EXPIRY_DAYS: int = 30
DEFAULT_DAILY_QUOTA: int = 15
MAINTENANCE_USERNAME: str = "codex-maintenance"


def _generate_session_token() -> str:
    """ランダムなセッショントークンを生成"""
    return str(uuid.uuid4())


# ============ ユーザー管理 ============


def register_user(
    username: str,
) -> tuple[bool, str, str | None]:
    """
    新規ユーザーを登録

    Returns:
        tuple: (success, message, user_id)
    """
    if not username:
        return False, "ユーザー名を入力してください", None

    if len(username) < 2:
        return False, "ユーザー名は2文字以上で入力してください", None

    supabase = get_supabase()

    # ユーザー名の重複チェック
    existing = (
        supabase.table("users").select("id").ilike("username", username).execute()
    )
    if existing.data:
        return False, "このユーザー名は既に使用されています", None

    result = (
        supabase.table("users")
        .insert(
            {
                "username": username,
                # 既存DBスキーマ互換用。アプリではパスワードを使わない。
                "password_hash": f"password_disabled_{uuid.uuid4().hex}",
            }
        )
        .execute()
    )

    if result.data:
        user_id: str = result.data[0]["id"]
        return True, "ユーザー登録が完了しました", user_id

    return False, "登録に失敗しました", None


# ============ ユーザー情報取得 ============


def get_all_users(*, include_maintenance: bool = False) -> list[dict[str, Any]]:
    """登録されているユーザー（id, username）を取得"""
    supabase = get_supabase()
    result = supabase.table("users").select("id, username").execute()
    users = result.data if result.data else []
    if include_maintenance:
        return users
    return [
        user
        for user in users
        if str(user.get("username", "")).casefold() != MAINTENANCE_USERNAME.casefold()
    ]


def get_or_create_maintenance_user() -> dict[str, Any]:
    """AI/Codex整備用の固定ユーザーを取得し、なければ作成する。"""
    supabase = get_supabase()
    existing = (
        supabase.table("users")
        .select("id, username")
        .ilike("username", MAINTENANCE_USERNAME)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    result = (
        supabase.table("users")
        .insert(
            {
                "username": MAINTENANCE_USERNAME,
                "password_hash": f"password_disabled_{uuid.uuid4().hex}",
            }
        )
        .execute()
    )
    if not result.data:
        raise RuntimeError("整備用ユーザーを作成できませんでした。")
    return result.data[0]


def login_user_direct(user_id: str) -> tuple[bool, str, str | None]:
    """パスワードなしでユーザーIDを指定して直接ログイン"""
    supabase = get_supabase()
    result = supabase.table("users").select("id").eq("id", user_id).execute()

    if not result.data:
        return False, "ユーザーが見つかりません", None

    return True, "ログイン成功", user_id


def get_username(user_id: str) -> str | None:
    """ユーザーIDからユーザー名を取得（セッションキャッシュ付き）"""
    cache_key = f"username_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    supabase = get_supabase()
    result = supabase.table("users").select("username").eq("id", user_id).execute()
    if result.data:
        username: str = result.data[0]["username"]
        st.session_state[cache_key] = username
        return username
    return None


# ============ ノルマ設定 ============


def get_daily_quota_limit(user_id: str) -> int:
    """ユーザーの1日のノルマ上限を取得（セッションキャッシュ）"""
    cache_key = f"daily_quota_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    supabase = get_supabase()
    result = supabase.table("users").select("daily_quota").eq("id", user_id).execute()

    if result.data and result.data[0].get("daily_quota") is not None:
        quota: int = result.data[0]["daily_quota"]
    else:
        quota = DEFAULT_DAILY_QUOTA

    st.session_state[cache_key] = quota
    return quota


def update_daily_quota_limit(user_id: str, limit: int) -> bool:
    """ユーザーの1日のノルマ上限を更新（DBとセッションキャッシュ）"""
    supabase = get_supabase()
    limit = int(limit)
    result = (
        supabase.table("users")
        .update({"daily_quota": limit})
        .eq("id", user_id)
        .execute()
    )

    st.session_state[f"daily_quota_{user_id}"] = limit
    return bool(result.data)


# ============ セッション管理 ============


def create_session(user_id: str) -> str:
    """
    新しいセッションを作成し、トークンを返す

    Returns:
        str: セッショントークン
    """
    supabase = get_supabase()
    token = _generate_session_token()

    # 有効期限を設定（現在時刻 + 30日）
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)

    supabase.table("sessions").insert(
        {"token": token, "user_id": user_id, "expires_at": expires_at.isoformat()}
    ).execute()

    return token


def validate_session_token(token: str) -> str | None:
    """
    セッショントークンを検証

    Returns:
        str or None: 有効な場合はuser_id、無効な場合はNone
    """
    if not token:
        return None

    supabase = get_supabase()

    result = (
        supabase.table("sessions")
        .select("user_id, expires_at")
        .eq("token", token)
        .execute()
    )

    if not result.data:
        return None

    session: dict[str, Any] = result.data[0]
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))

    # 有効期限チェック
    if datetime.now(timezone.utc) > expires_at:
        # 期限切れセッションを削除
        supabase.table("sessions").delete().eq("token", token).execute()
        return None

    return session["user_id"]


def delete_session(token: str) -> None:
    """セッションを削除（ログアウト用）"""
    if not token:
        return

    supabase = get_supabase()
    supabase.table("sessions").delete().eq("token", token).execute()


def cleanup_expired_sessions() -> None:
    """期限切れのセッションを削除"""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("sessions").delete().lt("expires_at", now).execute()
