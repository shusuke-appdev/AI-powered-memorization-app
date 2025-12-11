"""
Supabase データベース接続モジュール
"""
import os
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

def get_supabase() -> Client:
    """Supabaseクライアントを取得"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client
