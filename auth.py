"""
認証モジュール - Supabase版
ユーザー登録、ログイン、セッション管理
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from database import get_supabase

SESSION_EXPIRY_DAYS = 30

def hash_password(password):
    """パスワードをSHA-256でハッシュ化"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_session_token():
    """ランダムなセッショントークンを生成"""
    return str(uuid.uuid4())

# ============ ユーザー管理 ============

def register_user(username, password, api_key=""):
    """
    新規ユーザーを登録
    
    Returns:
        tuple: (success: bool, message: str, user_id: str or None)
    """
    if not username or not password:
        return False, "ユーザー名とパスワードを入力してください", None
    
    if len(username) < 2:
        return False, "ユーザー名は2文字以上で入力してください", None
    
    if len(password) < 4:
        return False, "パスワードは4文字以上で入力してください", None
    
    supabase = get_supabase()
    
    # ユーザー名の重複チェック
    existing = supabase.table("users").select("id").ilike("username", username).execute()
    if existing.data:
        return False, "このユーザー名は既に使用されています", None
    
    # 新規ユーザー作成
    result = supabase.table("users").insert({
        "username": username,
        "password_hash": hash_password(password),
        "api_key": api_key
    }).execute()
    
    if result.data:
        user_id = result.data[0]["id"]
        return True, "ユーザー登録が完了しました", user_id
    
    return False, "登録に失敗しました", None

def authenticate_user(username, password):
    """
    ユーザー認証
    
    Returns:
        tuple: (success: bool, message: str, user_id: str or None)
    """
    if not username or not password:
        return False, "ユーザー名とパスワードを入力してください", None
    
    supabase = get_supabase()
    password_hash = hash_password(password)
    
    result = supabase.table("users").select("id, password_hash").ilike("username", username).execute()
    
    if not result.data:
        return False, "ユーザーが見つかりません", None
    
    user = result.data[0]
    if user["password_hash"] == password_hash:
        return True, "ログイン成功", user["id"]
    else:
        return False, "パスワードが正しくありません", None

def get_username(user_id):
    """ユーザーIDからユーザー名を取得（セッションキャッシュ付き）"""
    import streamlit as st
    cache_key = f"username_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    supabase = get_supabase()
    result = supabase.table("users").select("username").eq("id", user_id).execute()
    if result.data:
        username = result.data[0]["username"]
        st.session_state[cache_key] = username
        return username
    return None

def get_api_key(user_id):
    """ユーザーIDからAPIキーを取得（セッションキャッシュ付き）"""
    import streamlit as st
    cache_key = f"api_key_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    supabase = get_supabase()
    result = supabase.table("users").select("api_key").eq("id", user_id).execute()
    if result.data:
        api_key = result.data[0].get("api_key", "")
        st.session_state[cache_key] = api_key
        return api_key
    return ""

def update_api_key(user_id, api_key):
    """ユーザーのAPIキーを更新"""
    import streamlit as st
    supabase = get_supabase()
    result = supabase.table("users").update({"api_key": api_key}).eq("id", user_id).execute()
    # キャッシュを更新
    st.session_state[f"api_key_{user_id}"] = api_key
    return bool(result.data)

# ============ ノルマ設定 ============

DEFAULT_DAILY_QUOTA = 15

def get_daily_quota_limit(user_id):
    """ユーザーの1日のノルマ上限を取得（セッションキャッシュ）"""
    import streamlit as st
    cache_key = f"daily_quota_{user_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    # デフォルト値を返す（DBにカラムがない場合のフォールバック）
    st.session_state[cache_key] = DEFAULT_DAILY_QUOTA
    return DEFAULT_DAILY_QUOTA

def update_daily_quota_limit(user_id, limit):
    """ユーザーの1日のノルマ上限を更新（セッションキャッシュのみ）"""
    import streamlit as st
    st.session_state[f"daily_quota_{user_id}"] = limit
    return True

# ============ セッション管理 ============

def create_session(user_id):
    """
    新しいセッションを作成し、トークンを返す
    
    Returns:
        str: セッショントークン
    """
    supabase = get_supabase()
    token = generate_session_token()
    
    # 有効期限を設定（現在時刻 + 30日）
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)
    
    result = supabase.table("sessions").insert({
        "token": token,
        "user_id": user_id,
        "expires_at": expires_at.isoformat()
    }).execute()
    
    return token

def validate_session_token(token):
    """
    セッショントークンを検証
    
    Returns:
        str or None: 有効な場合はuser_id、無効な場合はNone
    """
    if not token:
        return None
    
    supabase = get_supabase()
    
    result = supabase.table("sessions").select("user_id, expires_at").eq("token", token).execute()
    
    if not result.data:
        return None
    
    session = result.data[0]
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    
    # 有効期限チェック
    if datetime.now(timezone.utc) > expires_at:
        # 期限切れセッションを削除
        supabase.table("sessions").delete().eq("token", token).execute()
        return None
    
    return session["user_id"]

def delete_session(token):
    """セッションを削除（ログアウト用）"""
    if not token:
        return
    
    supabase = get_supabase()
    supabase.table("sessions").delete().eq("token", token).execute()

def cleanup_expired_sessions():
    """期限切れのセッションを削除"""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("sessions").delete().lt("expires_at", now).execute()
