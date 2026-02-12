"""
ストレージモジュール - Supabase版（キャッシュ最適化）
ユーザー別のカードデータ管理
"""
from datetime import date
import streamlit as st
from database import get_supabase
from utils import get_initial_card_state

# キャッシュのTTL（秒）
CACHE_TTL = 60

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load_cards_cached(user_id):
    """キャッシュ付きでカードを読み込む（内部用）"""
    supabase = get_supabase()
    
    result = supabase.table("cards").select("*").eq("user_id", user_id).execute()
    
    if not result.data:
        return []
    
    # データベースの形式をアプリの形式に変換
    cards = []
    for row in result.data:
        cards.append({
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "title": row.get("title", ""),
            "category": row.get("category", "その他"),
            "ease_factor": row.get("ease_factor", 2.5),
            "interval": row.get("interval", 1),
            "repetitions": row.get("repetitions", 0),
            "next_review": row.get("next_review", date.today().isoformat()),
            "source_id": row.get("source_id"),
            "blank_count": row.get("blank_count", 1),
            "is_favorite": row.get("is_favorite", False)
        })
    
    return cards

def load_cards(user_id):
    """指定ユーザーのカードを読み込む"""
    return _load_cards_cached(user_id)

def clear_cards_cache(user_id=None):
    """カードのキャッシュをクリア"""
    _load_cards_cached.clear()

def save_cards(user_id, cards):
    """指定ユーザーのカードを保存（一括更新用、通常は個別操作を使用）"""
    pass

def add_card(user_id, question, answer, title="", category="その他", source_id=None, blank_count=1):
    """カードを追加"""
    supabase = get_supabase()
    initial_state = get_initial_card_state()
    
    card_data = {
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "title": title,
        "category": category,
        "ease_factor": initial_state["ease_factor"],
        "interval": initial_state["interval"],
        "repetitions": initial_state["repetitions"],
        "next_review": initial_state["next_review"],
        "blank_count": blank_count
    }
    
    if source_id:
        card_data["source_id"] = source_id
    
    result = supabase.table("cards").insert(card_data).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)
    
    return result.data[0]["id"] if result.data else None

# ============ 原文カード管理 ============

def add_source_card(user_id, source_text, title="", category="その他"):
    """原文カードを追加"""
    supabase = get_supabase()
    
    result = supabase.table("source_cards").insert({
        "user_id": user_id,
        "source_text": source_text,
        "title": title,
        "category": category
    }).execute()
    
    # キャッシュをクリア
    clear_source_cards_cache(user_id)
    
    if result.data:
        return result.data[0]["id"]
    return None

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _load_source_cards_cached(user_id):
    """キャッシュ付きで原文カードを読み込む（内部用）"""
    supabase = get_supabase()
    
    result = supabase.table("source_cards").select("*").eq("user_id", user_id).execute()
    
    if not result.data:
        return []
    
    return result.data

def load_source_cards(user_id):
    """原文カードを読み込む"""
    return _load_source_cards_cached(user_id)

def clear_source_cards_cache(user_id=None):
    """原文カードのキャッシュをクリア"""
    _load_source_cards_cached.clear()

def get_source_card(source_id):
    """特定の原文カードを取得"""
    supabase = get_supabase()
    
    result = supabase.table("source_cards").select("*").eq("id", source_id).execute()
    
    if result.data:
        return result.data[0]
    return None

def get_source_cards_by_ids(source_ids):
    """複数の原文カードを取得"""
    if not source_ids:
        return []
    
    supabase = get_supabase()
    
    result = supabase.table("source_cards").select("*").in_("id", source_ids).execute()
    
    return result.data if result.data else []

def delete_source_card(user_id, source_id):
    """原文カードを削除"""
    supabase = get_supabase()
    
    supabase.table("source_cards").delete().eq("id", source_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_source_cards_cache(user_id)

def update_card_progress(user_id, card_id, stats):
    """カードの学習進捗を更新"""
    supabase = get_supabase()
    
    supabase.table("cards").update({
        "ease_factor": stats["ease_factor"],
        "interval": stats["interval"],
        "repetitions": stats["repetitions"],
        "next_review": stats["next_review"]
    }).eq("id", card_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def update_card_content(user_id, card_id, question, answer, title="", category="その他"):
    """カードの内容を更新"""
    supabase = get_supabase()
    
    supabase.table("cards").update({
        "question": question,
        "answer": answer,
        "title": title,
        "category": category
    }).eq("id", card_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def delete_card(user_id, card_id):
    """カードを削除"""
    supabase = get_supabase()
    
    supabase.table("cards").delete().eq("id", card_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def delete_cards_batch(user_id, card_ids):
    """複数のカードを一括削除"""
    if not card_ids:
        return
    
    supabase = get_supabase()
    
    # in_演算子で一括削除（パフォーマンス最適化）
    supabase.table("cards").delete().in_("id", card_ids).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def toggle_favorite(user_id, card_id, is_favorite):
    """カードのお気に入り状態をトグル"""
    supabase = get_supabase()
    
    supabase.table("cards").update({
        "is_favorite": is_favorite
    }).eq("id", card_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def toggle_favorite_by_source_id(user_id, source_id, is_favorite):
    """原文IDに紐づく全てのカードのお気に入り状態をトグル"""
    supabase = get_supabase()
    
    supabase.table("cards").update({
        "is_favorite": is_favorite
    }).eq("source_id", source_id).eq("user_id", user_id).execute()
    
    # キャッシュをクリア
    clear_cards_cache(user_id)

def get_favorite_cards(user_id):
    """お気に入りカードのみを取得"""
    cards = load_cards(user_id)
    return [c for c in cards if c.get("is_favorite", False)]

