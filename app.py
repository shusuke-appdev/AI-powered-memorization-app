import streamlit as st
import datetime
import os
from gemini_client import generate_flashcards
from storage import load_cards, add_card, update_card_progress, delete_card, update_card_content, delete_cards_batch
from utils import calculate_next_review
from auth import register_user, authenticate_user, get_username, create_session, validate_session_token, delete_session, get_api_key, update_api_key
from streamlit_cookies_controller import CookieController

# Page Config
st.set_page_config(
    page_title="AI 暗記カード",
    page_icon="🧠",
    layout="wide"
)

# Cookie Controller
cookie_controller = CookieController()

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #f8f9fa;
    }

    .flashcard {
        background-color: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 30px;
        border: 1px solid #eaeaea;
        transition: transform 0.2s;
        position: relative;
    }
    
    .flashcard-title {
        position: absolute;
        top: 10px;
        left: 20px;
        font-size: 14px;
        color: #9ca3af;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .flashcard-category {
        position: absolute;
        top: 10px;
        right: 20px;
        font-size: 12px;
        background-color: #e5e7eb;
        color: #374151;
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 600;
    }
    
    .flashcard:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px rgba(0,0,0,0.08);
    }

    .flashcard-question {
        font-size: 24px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 20px;
    }

    .flashcard-answer {
        font-size: 20px;
        color: #10b981;
        font-weight: 500;
        padding-top: 20px;
        border-top: 2px dashed #f3f4f6;
        margin-top: 20px;
    }

    .stButton button {
        border-radius: 12px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        border: none;
        transition: all 0.2s;
    }
    
    /* Tab Navigation Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: #ffffff;
        padding: 0;
        border-bottom: 3px solid #e5e7eb;
        margin-bottom: 30px;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: 24px;
        font-weight: 700;
        padding: 20px 40px;
        background-color: #f8f9fa;
        border-radius: 0;
        color: #6b7280;
        transition: all 0.3s;
        flex: 1;
        text-align: center;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e5e7eb;
        color: #1f2937;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #10b981;
        color: white;
    }
    
    /* Hide the red underline on active tab */
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
    
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    }

</style>
""", unsafe_allow_html=True)

# ============ 認証処理 ============

def check_auth():
    """認証状態をチェック"""
    # session_stateにログイン情報があるか確認
    if "user_id" in st.session_state and st.session_state.user_id:
        return True
    
    # Cookieからセッショントークンを取得
    session_token = cookie_controller.get("session_token")
    if session_token:
        user_id = validate_session_token(session_token)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.username = get_username(user_id)
            return True
    
    return False

def show_login_page():
    """ログイン/登録ページを表示"""
    st.title("🧠 AI 暗記カード")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### ログイン")
        
        # タブでログインと登録を切り替え
        login_tab, register_tab = st.tabs(["ログイン", "新規登録"])
        
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("ユーザー名", key="login_username")
                password = st.text_input("パスワード", type="password", key="login_password")
                remember_me = st.checkbox("ログイン状態を保持する", value=True)
                
                if st.form_submit_button("ログイン", type="primary", use_container_width=True):
                    success, message, user_id = authenticate_user(username, password)
                    if success:
                        st.session_state.user_id = user_id
                        st.session_state.username = username
                        
                        if remember_me:
                            # セッショントークンを作成してCookieに保存
                            token = create_session(user_id)
                            cookie_controller.set("session_token", token)
                        
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        with register_tab:
            with st.form("register_form"):
                new_username = st.text_input("ユーザー名", key="register_username")
                new_password = st.text_input("パスワード", type="password", key="register_password")
                confirm_password = st.text_input("パスワード（確認）", type="password", key="confirm_password")
                new_api_key = st.text_input("Gemini APIキー", type="password", key="register_api_key", help="Google GeminiのAPIキーを入力してください")
                
                if st.form_submit_button("登録", type="primary", use_container_width=True):
                    if new_password != confirm_password:
                        st.error("パスワードが一致しません")
                    else:
                        success, message, user_id = register_user(new_username, new_password, new_api_key)
                        if success:
                            st.session_state.user_id = user_id
                            st.session_state.username = new_username
                            
                            # 登録後も自動でログイン状態を保持
                            token = create_session(user_id)
                            cookie_controller.set("session_token", token)
                            
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

def logout():
    """ログアウト処理"""
    # セッショントークンを削除
    session_token = cookie_controller.get("session_token")
    if session_token:
        delete_session(session_token)
        cookie_controller.remove("session_token")
    
    # session_stateをクリア
    if "user_id" in st.session_state:
        del st.session_state.user_id
    if "username" in st.session_state:
        del st.session_state.username
    
    st.rerun()

# ============ メインアプリ ============

def show_main_app():
    """メインアプリケーションを表示"""
    user_id = st.session_state.user_id
    username = st.session_state.get("username", "ユーザー")
    
    # Header with logout
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("🧠 AI 暗記カード")
    with header_col2:
        st.markdown(f"**{username}** さん")
        if st.button("ログアウト"):
            logout()

    # API Key - ユーザーアカウントから読み込み
    user_api_key = get_api_key(user_id)
    
    # APIキー設定セクション
    with st.expander("⚙️ APIキー設定", expanded=not user_api_key):
        if user_api_key:
            st.success("✅ APIキーが設定されています")
            new_api_key = st.text_input("APIキーを変更", type="password", placeholder="新しいAPIキーを入力...", key="update_api_key_input")
            if st.button("APIキーを更新"):
                if new_api_key:
                    update_api_key(user_id, new_api_key)
                    st.success("APIキーを更新しました！")
                    st.rerun()
                else:
                    st.warning("新しいAPIキーを入力してください")
        else:
            st.warning("⚠️ APIキーが設定されていません。カード生成にはAPIキーが必要です。")
            new_api_key = st.text_input("Gemini APIキー", type="password", help="Google GeminiのAPIキーを入力してください", key="set_api_key_input")
            if st.button("APIキーを保存"):
                if new_api_key:
                    update_api_key(user_id, new_api_key)
                    st.success("APIキーを保存しました！")
                    st.rerun()
                else:
                    st.warning("APIキーを入力してください")
    
    # 使用するAPIキー
    api_key = user_api_key

    st.markdown("---")

    # Tab Navigation
    tab1, tab2, tab3 = st.tabs(["📚 復習する", "📝 カードを追加", "🗂️ カード管理"])

    # Review Page
    with tab1:
        st.title("復習セッション")
        
        cards = load_cards(user_id)
        today = datetime.date.today().isoformat()
        
        # Filter cards due for review
        due_cards = [c for c in cards if c['next_review'] <= today]
        
        if not due_cards:
            st.markdown("""
            <div style="text-align: center; padding: 50px;">
                <h2>🎉 復習完了！</h2>
                <p style="color: #6b7280;">今日復習すべきカードはすべて終わりました。お疲れ様でした！</p>
            </div>
            """, unsafe_allow_html=True)
            st.metric("デッキのカード総数", len(cards))
        else:
            progress = len(due_cards) / len(cards) if cards else 0
            st.progress(progress, text=f"今日の残り: {len(due_cards)} 枚")
            
            # Current card session state
            if "current_card_index" not in st.session_state:
                st.session_state.current_card_index = 0
                
            # Ensure index is valid
            if st.session_state.current_card_index >= len(due_cards):
                 st.session_state.current_card_index = 0
                 
            current_card = due_cards[st.session_state.current_card_index]
            
            # Card Display
            st.markdown(f"""
            <div class="flashcard">
                {f'<div class="flashcard-title">{current_card.get("title", "")}</div>' if current_card.get("title") else ''}
                {f'<div class="flashcard-category">{current_card.get("category", "その他")}</div>'}
                <div class="flashcard-question">{current_card['question']}</div>
                {f'<div class="flashcard-answer">{current_card["answer"]}</div>' if st.session_state.get("show_answer", False) else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # Controls
            if not st.session_state.get("show_answer", False):
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("答えを見る", type="primary", use_container_width=True):
                        st.session_state.show_answer = True
                        st.rerun()
            else:
                st.markdown("<div style='text-align: center; margin-bottom: 10px; color: #6b7280;'>どれくらい覚えていましたか？</div>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                
                def process_review(quality):
                    new_stats = calculate_next_review(quality, current_card)
                    update_card_progress(user_id, current_card['id'], new_stats)
                    st.session_state.show_answer = False
                    st.rerun()

                with col1:
                    if st.button("忘れた (0)", use_container_width=True):
                        process_review(0)
                with col2:
                    if st.button("難しい (3)", use_container_width=True):
                        process_review(3)
                with col3:
                    if st.button("普通 (4)", use_container_width=True):
                        process_review(4)
                with col4:
                    if st.button("簡単 (5)", type="primary", use_container_width=True):
                        process_review(5)

    # Add Cards Page
    with tab2:
        st.title("📝 新しいカードを追加")
        st.markdown("AIを使って、テキストから暗記カードを自動生成します。")
        
        # Category selection
        CATEGORIES = ["民法", "商法", "刑法", "憲法", "行政法", "民事訴訟法", "刑事訴訟法", "その他"]
        selected_category = st.selectbox("カテゴリ", CATEGORIES)

        # Title input (common for all generated cards)
        card_title = st.text_input("カードのタイトル（共通）", placeholder="例: Python基礎, 歴史年号")

        source_text = st.text_area("テキストを貼り付けてください:", height=400, placeholder="覚えたい記事、ノート、単語リストなどをここに貼り付けてください...")
        
        # Optional keyword input
        keywords = st.text_input("重要な用語（オプション）", placeholder="カンマ区切りで入力（例: Python, API, データベース）")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            generate_btn = st.button("✨ 生成する", type="primary")
        
        if generate_btn:
            if not api_key:
                st.error("Gemini APIキーを入力してください。")
            elif not source_text:
                st.warning("テキストを入力してください。")
            else:
                with st.spinner("Geminiがカードを生成中..."):
                    generated_cards = generate_flashcards(source_text, api_key, keywords)
                    
                    if generated_cards:
                        st.session_state.generated_cards = generated_cards
                        st.success(f"{len(generated_cards)} 枚のカードを生成しました！")
                    else:
                        st.error("カードの生成に失敗しました。もう一度試してください。")

        if "generated_cards" in st.session_state:
            st.subheader("プレビュー & 保存")
            
            with st.form("save_cards_form"):
                cards_to_save = []
                for i, card in enumerate(st.session_state.generated_cards):
                    st.markdown(f"**カード {i+1}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        q = st.text_input(f"問題", value=card['question'], key=f"q_{i}", label_visibility="collapsed", placeholder="問題")
                    with col2:
                        a = st.text_input(f"答え", value=card['answer'], key=f"a_{i}", label_visibility="collapsed", placeholder="答え")
                    cards_to_save.append({"question": q, "answer": a})
                    st.markdown("---")
                
                submit_col1, submit_col2 = st.columns([1, 4])
                with submit_col1:
                    if st.form_submit_button("💾 デッキに保存", type="primary"):
                        count = 0
                        for card in cards_to_save:
                            if card['question'] and card['answer']:
                                add_card(user_id, card['question'], card['answer'], title=card_title, category=selected_category)
                                count += 1
                        st.success(f"{count} 枚のカードを保存しました！")
                        del st.session_state.generated_cards
                        st.rerun()


    # Manage Cards Page
    with tab3:
        st.title("🗂️ カード管理")
        
        cards = load_cards(user_id)
        CATEGORIES = ["民法", "商法", "刑法", "憲法", "行政法", "民事訴訟法", "刑事訴訟法", "その他"]
        
        if not cards:
            st.info("まだカードがありません。「カードを追加」メニューから作成してください。")
        else:
            st.markdown(f"**登録済みカード: {len(cards)} 枚**")
            
            # Search box
            search_query = st.text_input("🔍 検索", placeholder="問題、答え、タイトルで検索...", key="search_cards")
            
            # Filter cards by search query
            if search_query:
                filtered_cards = []
                for card in cards:
                    query_lower = search_query.lower()
                    if (query_lower in card['question'].lower() or 
                        query_lower in card['answer'].lower() or 
                        query_lower in card.get('title', '').lower()):
                        filtered_cards.append(card)
                cards = filtered_cards
                st.markdown(f"*検索結果: {len(filtered_cards)} 枚*")
            
            # Group cards by category
            tabs = st.tabs(CATEGORIES)
            
            for i, category in enumerate(CATEGORIES):
                with tabs[i]:
                    category_cards = [c for c in cards if c.get("category", "その他") == category]
                    
                    if not category_cards:
                        st.info(f"{category} のカードはありません。")
                    else:
                        # Group cards by title
                        grouped_cards = {}
                        for card in category_cards:
                            title = card.get('title', '').strip()
                            if not title:
                                title = "📝 無題"
                            if title not in grouped_cards:
                                grouped_cards[title] = []
                            grouped_cards[title].append(card)
                        
                        # Display cards grouped by title
                        for title, cards_in_group in grouped_cards.items():
                            # Create a unique key for this group
                            group_key = f"{category}_{title}".replace(" ", "_")
                            
                            # Group header with batch delete button
                            header_col1, header_col2 = st.columns([4, 1])
                            with header_col1:
                                expander_open = st.checkbox(f"📚 {title} ({len(cards_in_group)}枚)", key=f"expand_{group_key}")
                            with header_col2:
                                # Batch delete button for the group
                                if st.button("🗑️ 全削除", key=f"batch_del_{group_key}", type="secondary"):
                                    st.session_state[f"confirm_batch_del_{group_key}"] = True
                            
                            # Batch delete confirmation
                            if st.session_state.get(f"confirm_batch_del_{group_key}", False):
                                st.warning(f"⚠️ 「{title}」のカード {len(cards_in_group)} 枚を全て削除しますか？")
                                confirm_col1, confirm_col2, confirm_col3 = st.columns([1, 1, 3])
                                with confirm_col1:
                                    if st.button("✓ 削除する", key=f"confirm_yes_{group_key}", type="primary"):
                                        card_ids = [c['id'] for c in cards_in_group]
                                        delete_cards_batch(user_id, card_ids)
                                        del st.session_state[f"confirm_batch_del_{group_key}"]
                                        st.success(f"{len(cards_in_group)} 枚のカードを削除しました")
                                        st.rerun()
                                with confirm_col2:
                                    if st.button("✗ キャンセル", key=f"confirm_no_{group_key}"):
                                        del st.session_state[f"confirm_batch_del_{group_key}"]
                                        st.rerun()
                            
                            # Show cards if expander is open
                            if expander_open:
                                st.markdown("---")
                                for j, card in enumerate(cards_in_group):
                                    st.markdown(f"**カード {j+1}**: {card['question'][:50]}...")
                                    
                                    # Edit form
                                    with st.form(key=f"edit_form_{card['id']}"):
                                        new_category = st.selectbox("カテゴリ", CATEGORIES, index=CATEGORIES.index(card.get("category", "その他")), key=f"cat_{card['id']}")
                                        new_title = st.text_input("タイトル", value=card.get('title', ''), key=f"title_{card['id']}")
                                        new_q = st.text_input("問題", value=card['question'], key=f"q_{card['id']}")
                                        new_a = st.text_input("答え", value=card['answer'], key=f"a_{card['id']}")
                                        
                                        if st.form_submit_button("✓ 更新", type="primary"):
                                            update_card_content(user_id, card['id'], new_q, new_a, new_title, new_category)
                                            st.success("カードを更新しました")
                                            st.rerun()
                                    
                                    # Individual delete button (outside form)
                                    if st.button("🗑️ このカードを削除", key=f"del_btn_{card['id']}", type="secondary"):
                                        st.session_state[f"confirm_del_{card['id']}"] = True
                                    
                                    # Delete confirmation for individual card
                                    if st.session_state.get(f"confirm_del_{card['id']}", False):
                                        st.warning("⚠️ このカードを削除しますか？")
                                        del_col1, del_col2, del_col3 = st.columns([1, 1, 3])
                                        with del_col1:
                                            if st.button("✓ 削除", key=f"confirm_del_yes_{card['id']}", type="primary"):
                                                delete_card(user_id, card['id'])
                                                del st.session_state[f"confirm_del_{card['id']}"]
                                                st.success("カードを削除しました")
                                                st.rerun()
                                        with del_col2:
                                            if st.button("✗ 戻る", key=f"confirm_del_no_{card['id']}"):
                                                del st.session_state[f"confirm_del_{card['id']}"]
                                                st.rerun()
                                    
                                    if j < len(cards_in_group) - 1:
                                        st.markdown("---")
                                st.markdown("")  # Add spacing after group

# ============ アプリケーション実行 ============

if check_auth():
    show_main_app()
else:
    show_login_page()
