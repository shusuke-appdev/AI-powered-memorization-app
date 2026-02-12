"""
Supabase データベース接続モジュール
"""
import os
import time
from supabase import create_client, Client

# Supabase接続情報
# 環境変数 または Streamlit secrets から読み込み
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Streamlit secrets からも読み込み試行
try:
    import streamlit as st
    if hasattr(st, 'secrets'):
        if "SUPABASE_URL" in st.secrets:
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets:
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    pass

# Supabaseクライアント（シングルトン）
_supabase_client: Client = None

# リトライ設定
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒

class DatabaseConnectionError(Exception):
    """データベース接続エラー"""
    def __init__(self, message="データベースに接続できません"):
        self.message = message
        super().__init__(self.message)

def get_supabase() -> Client:
    """
    Supabaseクライアントを取得（リトライロジック付き）
    
    Raises:
        DatabaseConnectionError: 接続に失敗した場合
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    # 設定チェック
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise DatabaseConnectionError(
            "データベース設定が見つかりません。SUPABASE_URLとSUPABASE_KEYを設定してください。"
        )
    
    # リトライ付きで接続
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            return _supabase_client
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    # 全リトライ失敗
    error_msg = str(last_error).lower() if last_error else ""
    if "connect" in error_msg or "timeout" in error_msg:
        raise DatabaseConnectionError(
            "データベースサーバーに接続できません。インターネット接続を確認するか、しばらく待ってから再試行してください。"
        )
    elif "unauthorized" in error_msg or "401" in error_msg:
        raise DatabaseConnectionError(
            "データベースの認証に失敗しました。APIキーを確認してください。"
        )
    else:
        raise DatabaseConnectionError(
            f"データベースエラー: {last_error}"
        )

def reset_connection():
    """接続をリセット（エラー発生時の再接続用）"""
    global _supabase_client
    _supabase_client = None

