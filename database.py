"""
Supabase データベース接続モジュール
"""

from __future__ import annotations

import os
import time
from typing import Any

from supabase import Client, create_client


class DatabaseConnectionError(Exception):
    """データベース接続エラー"""

    def __init__(self, message: str = "データベースに接続できません") -> None:
        self.message = message
        super().__init__(self.message)


# リトライ設定
_MAX_RETRIES: int = 3
_RETRY_DELAY: float = 1.0  # 秒

# Supabaseクライアント（シングルトン）
_supabase_client: Client | None = None


def _resolve_credentials() -> tuple[str, str]:
    """
    環境変数またはStreamlit secretsからSupabase接続情報を解決する。

    Streamlitのhot-reloadでモジュールレベルの変数が固定される問題を回避するため、
    毎回ランタイムで解決する。
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            if "SUPABASE_URL" in st.secrets:
                url = st.secrets["SUPABASE_URL"]
            if "SUPABASE_KEY" in st.secrets:
                key = st.secrets["SUPABASE_KEY"]
    except Exception:
        pass

    return url, key


def get_supabase() -> Client:
    """
    Supabaseクライアントを取得（リトライロジック付き）

    Raises:
        DatabaseConnectionError: 接続に失敗した場合
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    url, key = _resolve_credentials()

    if not url or not key:
        raise DatabaseConnectionError(
            "データベース設定が見つかりません。SUPABASE_URLとSUPABASE_KEYを設定してください。"
        )

    # リトライ付きで接続
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            _supabase_client = create_client(url, key)
            return _supabase_client
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)

    # 全リトライ失敗
    _raise_connection_error(last_error)
    # unreachable, but satisfies type checker
    raise DatabaseConnectionError()  # pragma: no cover


def _raise_connection_error(last_error: Exception | None) -> Any:
    """接続エラーの種別に応じた例外を送出"""
    error_msg = str(last_error).lower() if last_error else ""
    if "connect" in error_msg or "timeout" in error_msg:
        raise DatabaseConnectionError(
            "データベースサーバーに接続できません。インターネット接続を確認するか、しばらく待ってから再試行してください。"
        )
    elif "unauthorized" in error_msg or "401" in error_msg:
        raise DatabaseConnectionError(
            "データベースの認証に失敗しました。Supabase接続キーを確認してください。"
        )
    else:
        raise DatabaseConnectionError(f"データベースエラー: {last_error}")


def reset_connection() -> None:
    """接続をリセット（エラー発生時の再接続用）"""
    global _supabase_client
    _supabase_client = None
