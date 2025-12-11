"""
ストレージモジュール - Supabase版
ユーザー別のカードデータ管理
"""
from datetime import date
from database import get_supabase
from utils import get_initial_card_state

def load_cards(user_id):
    """指定ユーザーのカードを読み込む"""
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
            "next_review": row.get("next_review", date.today().isoformat())
        })
    
    return cards

def save_cards(user_id, cards):
    """指定ユーザーのカードを保存（一括更新用、通常は個別操作を使用）"""
    # Supabaseでは個別のCRUD操作を使用するため、この関数は互換性のために残す
    pass

def add_card(user_id, question, answer, title="", category="その他"):
    """ユーザーのカードを追加"""
    supabase = get_supabase()
    
    initial_state = get_initial_card_state()
    
    result = supabase.table("cards").insert({
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "title": title,
        "category": category,
        "ease_factor": initial_state["ease_factor"],
        "interval": initial_state["interval"],
        "repetitions": initial_state["repetitions"],
        "next_review": initial_state["next_review"]
    }).execute()
    
    if result.data:
        row = result.data[0]
        return {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "title": row.get("title", ""),
            "category": row.get("category", "その他"),
            **initial_state
        }
    return None

def update_card_progress(user_id, card_id, new_state):
    """ユーザーのカードの進捗を更新"""
    supabase = get_supabase()
    
    update_data = {}
    if "ease_factor" in new_state:
        update_data["ease_factor"] = new_state["ease_factor"]
    if "interval" in new_state:
        update_data["interval"] = new_state["interval"]
    if "repetitions" in new_state:
        update_data["repetitions"] = new_state["repetitions"]
    if "next_review" in new_state:
        update_data["next_review"] = new_state["next_review"]
    
    if update_data:
        supabase.table("cards").update(update_data).eq("id", card_id).eq("user_id", user_id).execute()

def delete_card(user_id, card_id):
    """ユーザーのカードを削除"""
    supabase = get_supabase()
    supabase.table("cards").delete().eq("id", card_id).eq("user_id", user_id).execute()

def delete_cards_batch(user_id, card_ids):
    """ユーザーのカードを一括削除"""
    supabase = get_supabase()
    for card_id in card_ids:
        supabase.table("cards").delete().eq("id", card_id).eq("user_id", user_id).execute()

def update_card_content(user_id, card_id, question, answer, title="", category="その他"):
    """ユーザーのカードの内容を更新"""
    supabase = get_supabase()
    
    supabase.table("cards").update({
        "question": question,
        "answer": answer,
        "title": title,
        "category": category
    }).eq("id", card_id).eq("user_id", user_id).execute()
