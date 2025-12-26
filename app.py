import streamlit as st
import datetime
import os
from gemini_client import generate_flashcards, help_chat
from storage import load_cards, add_card, update_card_progress, delete_card, update_card_content, delete_cards_batch, add_source_card, get_source_cards_by_ids, load_source_cards, delete_source_card
from utils import calculate_next_review, select_hybrid_quota
from auth import register_user, authenticate_user, get_username, create_session, validate_session_token, delete_session, get_api_key, update_api_key, get_daily_quota_limit, update_daily_quota_limit
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
        top: 12px;
        left: 20px;
        font-size: 16px;
        color: #059669;
        font-weight: 700;
        text-transform: none;
        letter-spacing: 0;
        background-color: #d1fae5;
        padding: 4px 12px;
        border-radius: 8px;
        border: 1px solid #10b981;
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
    
    /* Primary button - 緑色 */
    .stButton button[kind="primary"],
    .stButton button[data-testid="baseButton-primary"] {
        background-color: #10b981 !important;
        color: white !important;
    }
    
    .stButton button[kind="primary"]:hover,
    .stButton button[data-testid="baseButton-primary"]:hover {
        background-color: #059669 !important;
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
    
    /* 文節ブロックのスタイル */
    .phrase-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 20px 0;
    }
    
    .phrase-block {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 16px;
        transition: all 0.2s;
        border: 2px solid transparent;
    }
    
    .phrase-block.unselected {
        background-color: #e5e7eb;
        color: #374151;
    }
    
    .phrase-block.unselected:hover {
        background-color: #d1d5db;
        border-color: #10b981;
    }
    
    .phrase-block.selected {
        background-color: #10b981;
        color: white;
    }
    
    .phrase-block.selected:hover {
        background-color: #059669;
    }
    
    .phrase-block.punctuation {
        background-color: transparent;
        color: #6b7280;
        cursor: default;
        padding: 8px 4px;
    }
    
    /* Stylish phrase toggle grid */
    .phrase-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        padding: 20px;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        margin: 20px 0;
    }
    
    .phrase-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 18px;
        border-radius: 12px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 2px solid transparent;
        user-select: none;
    }
    
    .phrase-toggle.normal {
        background: white;
        color: #374151;
        border-color: #e5e7eb;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .phrase-toggle.normal:hover {
        border-color: #10b981;
        background: #f0fdf4;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(16,185,129,0.15);
    }
    
    .phrase-toggle.selected {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border-color: #059669;
        box-shadow: 0 4px 12px rgba(16,185,129,0.3);
    }
    
    .phrase-toggle.selected:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        transform: translateY(-1px);
    }
    
    .phrase-toggle.punct {
        background: transparent;
        color: #9ca3af;
        border: none;
        padding: 10px 4px;
        cursor: default;
        box-shadow: none;
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
    
    # API Key - ユーザーアカウントから読み込み
    user_api_key = get_api_key(user_id)
    api_key = user_api_key
    
    # ============ サイドバー（常時展開） ============
    
    # サイドバースタイル
    st.markdown("""
    <style>
    /* サイドバー幅設定 - 常時展開、幅を大きく */
    [data-testid="stSidebar"] {
        min-width: 350px !important;
        max-width: 350px !important;
    }
    
    /* 折りたたみボタンを非表示 */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* サイドバーの背景色を薄いグレーに */
    [data-testid="stSidebar"] > div:first-child {
        background: #f3f4f6 !important;
        padding: 1rem !important;
    }
    
    /* サイドバー内のテキスト色を黒に */
    [data-testid="stSidebar"] * {
        color: #1f2937 !important;
    }
    
    /* ボタンスタイル */
    [data-testid="stSidebar"] .stButton button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
    }
    [data-testid="stSidebar"] hr {
        border-color: #d1d5db;
        margin: 0.5rem 0;
    }
    
    /* 入力フィールド - 大きく */
    [data-testid="stSidebar"] .stTextInput input {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        color: #1f2937 !important;
        border-radius: 12px;
        padding: 16px !important;
        font-size: 15px !important;
        height: 50px !important;
    }
    [data-testid="stSidebar"] .stNumberInput input {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        color: #1f2937 !important;
    }
    
    /* チャット履歴コンテナの枠を削除 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        border: none !important;
        background: transparent !important;
    }
    
    /* ヘルプAIタイトル */
    .help-ai-title {
        font-size: 13px;
        font-weight: 600;
        color: #10b981 !important;
        margin-bottom: 8px;
    }
    
    /* チャットメッセージ */
    .chat-message {
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 6px;
        font-size: 13px;
        line-height: 1.4;
    }
    .chat-message.user {
        background: #e5e7eb;
        margin-left: 15px;
        border-left: 3px solid #6b7280;
    }
    .chat-message.assistant {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        margin-right: 15px;
        border-left: 3px solid #10b981;
        color: #065f46 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        # ユーザー情報セクション（最上部）
        st.markdown(f"### 👤 {username} さん")
        st.markdown("---")
        
        # APIキー設定セクション（コンパクト）
        st.markdown("##### ⚙️ APIキー設定")
        if user_api_key:
            st.success("✅ 設定済み")
            with st.expander("キーを変更", expanded=False):
                new_api_key = st.text_input("新しいAPIキー", type="password", placeholder="AIza...", key="sidebar_api_key_input")
                if st.button("更新", key="sidebar_update_api"):
                    if new_api_key:
                        update_api_key(user_id, new_api_key)
                        st.success("更新しました！")
                        st.rerun()
        else:
            st.warning("⚠️ 未設定")
            new_api_key = st.text_input("Gemini APIキー", type="password", placeholder="AIza...", key="sidebar_set_api_key")
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("保存", key="sidebar_save_api"):
                    if new_api_key:
                        update_api_key(user_id, new_api_key)
                        st.success("保存しました！")
                        st.rerun()
            with col2:
                st.markdown("[🔗 取得](https://aistudio.google.com/)")
        
        st.markdown("---")
        
        # ノルマ設定（コンパクト・横並び）
        col_label, col_input = st.columns([1, 1])
        with col_label:
            st.markdown("##### 📊 ノルマ")
        with col_input:
            current_quota = get_daily_quota_limit(user_id)
            new_quota = st.number_input(
                "上限",
                min_value=1,
                max_value=100,
                value=current_quota,
                step=1,
                key="sidebar_quota",
                label_visibility="collapsed"
            )
            if new_quota != current_quota:
                update_daily_quota_limit(user_id, new_quota)
                st.rerun()
        
        st.markdown("---")
        
        # ヘルプAI チャットセクション
        st.markdown("<div class='help-ai-title'>🤖 ヘルプAI</div>", unsafe_allow_html=True)
        
        # チャット履歴の初期化
        if "help_chat_history" not in st.session_state:
            st.session_state.help_chat_history = []
        
        # チャット履歴表示（大きなコンテナ）
        chat_container = st.container(height=450)
        with chat_container:
            if not st.session_state.help_chat_history:
                st.markdown("<div style='color: #6b7280; font-size: 13px; padding: 10px;'>💬 アプリの使い方について質問してください</div>", unsafe_allow_html=True)
            else:
                for msg in st.session_state.help_chat_history:
                    if msg["role"] == "user":
                        st.markdown(f"<div class='chat-message user'>🧑 {msg['content']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='chat-message assistant'>🤖 {msg['content']}</div>", unsafe_allow_html=True)
        
        # 質問入力（フォームで送信）
        with st.form(key="help_chat_form", clear_on_submit=True):
            user_question = st.text_area(
                "質問を入力",
                placeholder="質問を入力... (Ctrl+Enterで送信)",
                key="help_question_input",
                label_visibility="collapsed",
                height=215
            )
            submitted = st.form_submit_button("送信", use_container_width=True)
            
            if submitted and user_question and user_question.strip():
                if not api_key:
                    st.error("APIキーを設定してください")
                else:
                    st.session_state.help_chat_history.append({"role": "user", "content": user_question})
                    with st.spinner("回答中..."):
                        result = help_chat(user_question, api_key, st.session_state.help_chat_history[:-1])
                    if result["success"]:
                        st.session_state.help_chat_history.append({"role": "assistant", "content": result["response"]})
                    else:
                        st.session_state.help_chat_history.append({"role": "assistant", "content": f"⚠️ {result['error']}"})
                    st.rerun()
        
        # 履歴クリアボタン（コンパクト）
        if st.session_state.help_chat_history:
            if st.button("🗑️ 履歴クリア", key="clear_chat"):
                st.session_state.help_chat_history = []
                st.rerun()
        
        # ログアウトボタン（下部）
        st.markdown("---")
        if st.button("🚪 ログアウト", use_container_width=True, key="sidebar_logout"):
            logout()
    
    # ============ メインコンテンツ ============
    
    # タイトル
    st.title("🧠 AI 暗記カード")
    
    # Tab Navigation
    tab1, tab2, tab3 = st.tabs(["📚 本日のノルマ", "📝 カードを追加", "🗂️ カード管理"])

    # Review Page
    with tab1:
        st.title("本日のノルマ")
        
        cards = load_cards(user_id)
        today = datetime.date.today().isoformat()
        daily_limit = get_daily_quota_limit(user_id)
        
        # 日付が変わったらセッションをリセット
        if st.session_state.get("quota_date") != today:
            st.session_state.quota_date = today
            st.session_state.reviewed_source_ids = []
            st.session_state.reviewed_card_count = 0
        
        # 復習済みのsource_idを取得
        reviewed_source_ids = set(st.session_state.get("reviewed_source_ids", []))
        
        # Filter cards due for review（復習済みのsource_idを除外）
        all_due_cards = [c for c in cards if c['next_review'] <= today]
        available_due_cards = [c for c in all_due_cards if c.get('source_id') not in reviewed_source_ids or c.get('source_id') is None]
        
        # Apply hybrid quota selection algorithm
        # 残りのノルマ枚数を計算
        reviewed_count = st.session_state.get("reviewed_card_count", 0)
        remaining_limit = max(0, daily_limit - reviewed_count)
        due_cards = select_hybrid_quota(available_due_cards, remaining_limit, cards)
        
        if not due_cards:
            st.markdown("""
            <div style="text-align: center; padding: 50px;">
                <h2>🎉 本日のノルマ完了！</h2>
                <p style="color: #6b7280;">今日のノルマは終了しました。お疲れ様でした！</p>
            </div>
            """, unsafe_allow_html=True)
            st.metric("デッキのカード総数", len(cards))
            if len(all_due_cards) > daily_limit:
                st.info(f"💡 残り {len(all_due_cards) - daily_limit} 枚のカードが復習待ちです（明日以降）")
            
            # ノルマ復習モード（原文カードレビュー）
            reviewed_source_ids = st.session_state.get("reviewed_source_ids", [])
            if reviewed_source_ids:
                st.markdown("---")
                st.subheader("📖 ノルマ復習（原文確認）")
                st.markdown("今日復習したカードの原文を確認できます。")
                
                # 原文カードを取得
                source_cards = get_source_cards_by_ids(list(set(reviewed_source_ids)))
                
                if source_cards:
                    # 復習モードのセッション状態
                    if "source_review_index" not in st.session_state:
                        st.session_state.source_review_index = 0
                    
                    if st.session_state.source_review_index >= len(source_cards):
                        st.session_state.source_review_index = 0
                    
                    current_source = source_cards[st.session_state.source_review_index]
                    
                    st.progress(
                        (st.session_state.source_review_index + 1) / len(source_cards),
                        text=f"原文 {st.session_state.source_review_index + 1} / {len(source_cards)}"
                    )
                    
                    # 原文表示
                    st.markdown(f"""
                    <div class="flashcard">
                        {f'<div class="flashcard-title">{current_source.get("title", "")}</div>' if current_source.get("title") else ''}
                        {f'<div class="flashcard-category">{current_source.get("category", "その他")}</div>'}
                        <div class="flashcard-question" style="font-size: 18px; text-align: left;">{current_source.get("source_text", "")}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # ナビゲーション
                    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
                    with nav_col1:
                        if st.session_state.source_review_index > 0:
                            if st.button("◀ 前へ", use_container_width=True):
                                st.session_state.source_review_index -= 1
                                st.rerun()
                    with nav_col2:
                        if st.button("✓ 復習を終了", type="primary", use_container_width=True):
                            st.session_state.reviewed_source_ids = []
                            st.session_state.source_review_index = 0
                            st.rerun()
                    with nav_col3:
                        if st.session_state.source_review_index < len(source_cards) - 1:
                            if st.button("次へ ▶", use_container_width=True):
                                st.session_state.source_review_index += 1
                                st.rerun()
                else:
                    st.info("原文カードが見つかりませんでした。")
                    if st.button("クリア"):
                        st.session_state.reviewed_source_ids = []
                        st.rerun()
        else:
            reviewed_count = st.session_state.get("reviewed_card_count", 0)
            remaining = min(len(due_cards), daily_limit - reviewed_count)
            progress = reviewed_count / daily_limit if daily_limit > 0 else 0
            st.progress(progress, text=f"本日の進捗: {reviewed_count} / {daily_limit} 枚完了（残り {remaining} 枚）")
            
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
                    # 復習したカードのsource_idを追跡
                    source_id = current_card.get('source_id')
                    if source_id:
                        if "reviewed_source_ids" not in st.session_state:
                            st.session_state.reviewed_source_ids = []
                        if source_id not in st.session_state.reviewed_source_ids:
                            st.session_state.reviewed_source_ids.append(source_id)
                            # 復習済みカード数をインクリメント（同一原文での初回のみ）
                            st.session_state.reviewed_card_count = st.session_state.get("reviewed_card_count", 0) + 1
                    
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
        # 入力フィールドのセッションステート初期化
        if "add_card_category" not in st.session_state:
            st.session_state.add_card_category = ""
        if "add_card_title" not in st.session_state:
            st.session_state.add_card_title = ""
        if "add_card_text" not in st.session_state:
            st.session_state.add_card_text = ""
        if "widget_key_counter" not in st.session_state:
            st.session_state.widget_key_counter = 0
        
        # タイトルとキャンセルボタン
        title_col, cancel_col = st.columns([3, 1])
        with title_col:
            st.title("📝 新しいカードを追加")
        with cancel_col:
            st.markdown("")  # スペーサー
            # 工程が進んでいる場合のみキャンセルボタンを表示
            has_progress = "phrases" in st.session_state or "generated_cards" in st.session_state or st.session_state.add_card_text
            if has_progress:
                if st.button("🔄 クリア", type="secondary", use_container_width=True):
                    # 全ての関連セッション状態をクリア
                    if "phrases" in st.session_state:
                        del st.session_state.phrases
                    if "selected_indices" in st.session_state:
                        del st.session_state.selected_indices
                    if "generated_cards" in st.session_state:
                        del st.session_state.generated_cards
                    # 入力フィールドもクリア
                    st.session_state.add_card_category = ""
                    st.session_state.add_card_title = ""
                    st.session_state.add_card_text = ""
                    st.rerun()
        
        # Category selection
        CATEGORIES = ["民法", "商法", "刑法", "憲法", "行政法", "民事訴訟法", "刑事訴訟法", "その他"]
        CATEGORIES_WITH_PLACEHOLDER = ["-- カテゴリを選択 --"] + CATEGORIES
        current_idx = 0
        if st.session_state.add_card_category and st.session_state.add_card_category in CATEGORIES:
            current_idx = CATEGORIES_WITH_PLACEHOLDER.index(st.session_state.add_card_category)
        selected_category_raw = st.selectbox("カテゴリ", CATEGORIES_WITH_PLACEHOLDER, index=current_idx, key=f"category_select_{st.session_state.widget_key_counter}")
        selected_category = selected_category_raw if selected_category_raw != "-- カテゴリを選択 --" else ""
        st.session_state.add_card_category = selected_category

        # Title input with autocomplete disabled
        st.markdown("""
        <style>
        input[data-testid="stTextInput"][aria-label*="タイトル"] {
            autocomplete: off;
        }
        </style>
        """, unsafe_allow_html=True)
        
        card_title = st.text_input("カードのタイトル（共通）", value=st.session_state.add_card_title, placeholder="例: 不法行為, 契約総論", key=f"title_input_{st.session_state.widget_key_counter}", autocomplete="off")
        st.session_state.add_card_title = card_title
        
        # ステップ1: テキスト入力
        st.subheader("① テキストを入力")
        
        # 手動/AI切り替え
        if "manual_mode" not in st.session_state:
            st.session_state.manual_mode = False
        
        manual_mode = st.checkbox("✍️ 手動で穴埋め箇所を指定する（【】で囲む）", value=st.session_state.manual_mode, key="manual_mode_checkbox")
        st.session_state.manual_mode = manual_mode
        
        if manual_mode:
            st.info("💡 穴埋めにしたい箇所を【】で囲んでください。例: 民法【709条】は...")
        
        source_text = st.text_area(
            "",
            value=st.session_state.add_card_text,
            height=200,
            placeholder="例: 民法第709条は不法行為による損害賠償を規定している。\n\n手動モード時: 民法【709条】は【不法行為】による【損害賠償】を規定している。",
            key=f"text_input_{st.session_state.widget_key_counter}",
            label_visibility="collapsed"
        )
        st.session_state.add_card_text = source_text
        
        # インポート
        from gemini_client import split_into_phrases, suggest_blanks, generate_cards_from_selection, parse_blanks_from_text
        
        if manual_mode:
            # 手動モード: 【】マーカーで直接カード生成
            if st.button("✨ カード生成", type="primary", key="manual_generate_btn"):
                if not source_text:
                    st.warning("テキストを入力してください。")
                elif "【" not in source_text or "】" not in source_text:
                    st.warning("【】で穴埋め箇所を指定してください。例: 民法【709条】は...")
                else:
                    cards = parse_blanks_from_text(source_text)
                    if cards:
                        st.session_state.generated_cards = cards
                        st.success(f"{len(cards)} 枚のカードを生成しました！")
                    else:
                        st.error("カードの生成に失敗しました。【】で穴埋め箇所を正しく指定してください。")
        else:
            # AIモード: 文節分割ボタン
            if st.button("📝 テキストを解析", type="primary"):
                if not source_text:
                    st.warning("テキストを入力してください。")
                elif not api_key:
                    st.warning("APIキーを設定してください。")
                else:
                    with st.spinner("AIがテキストを解析中..."):
                        phrases = split_into_phrases(source_text, api_key)
                        # エラーチェック
                        if isinstance(phrases, dict) and phrases.get("error") == "API_QUOTA_EXCEEDED":
                            st.error(f"⚠️ {phrases.get('message', 'APIの利用制限に達しました。')}")
                        elif phrases:
                            st.session_state.phrases = phrases
                            st.session_state.selected_indices = []
                            st.success(f"{len(phrases)}個の文節に分割しました。穴埋め箇所を選択してください。")
                        else:
                            st.error("テキストの解析に失敗しました。")
        
        # ステップ2: 穴埋め箇所を選択
        if "phrases" in st.session_state and st.session_state.phrases:
            st.subheader("② 穴埋め箇所を選択")
            st.markdown("チェックを入れた箇所が穴埋め（______）になります。")
            
            phrases = st.session_state.phrases
            
            # AIに提案させるボタン
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🤖 AIに提案させる"):
                    if api_key:
                        with st.spinner("AIが提案中..."):
                            suggested = suggest_blanks(phrases, api_key)
                            # エラーチェック
                            if isinstance(suggested, dict) and suggested.get("error") == "API_QUOTA_EXCEEDED":
                                st.error(f"⚠️ {suggested.get('message', 'APIの利用制限に達しました。')}")
                            else:
                                st.session_state.selected_indices = suggested
                                st.rerun()
                    else:
                        st.warning("APIキーを設定してください。")
            
            # クリック式ブロックで文節を選択
            import re
            punctuation_pattern = r'^[。、，．,.！？!?：:；;\s①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]+$'
            
            # 初期化
            if "selected_indices" not in st.session_state:
                st.session_state.selected_indices = []
            
            # クリックでトグルする関数
            def toggle_phrase(idx):
                if idx in st.session_state.selected_indices:
                    st.session_state.selected_indices.remove(idx)
                else:
                    st.session_state.selected_indices.append(idx)
            
            # 文節をクリック可能なボタンとして表示
            st.markdown("**クリックで穴埋め箇所を選択:**")
            
            # ボタングリッドを作成（5列）
            cols_per_row = 5
            phrase_buttons_html = []
            
            for i, phrase in enumerate(phrases):
                is_punctuation = re.match(punctuation_pattern, phrase)
                is_selected = i in st.session_state.selected_indices
                
                if is_punctuation:
                    phrase_buttons_html.append(f"<span class='phrase-toggle punct'>{phrase}</span>")
                elif is_selected:
                    phrase_buttons_html.append(f"<span class='phrase-toggle selected' data-idx='{i}'>{phrase}</span>")
                else:
                    phrase_buttons_html.append(f"<span class='phrase-toggle normal' data-idx='{i}'>{phrase}</span>")
            
            # HTMLでプレビュー表示
            st.markdown(f"<div class='phrase-grid'>{''.join(phrase_buttons_html)}</div>", unsafe_allow_html=True)
            
            # Streamlit button で実際のトグル実装
            st.markdown("---")
            
            # 選択可能な文節のみボタン化（句読点以外）
            selectable_phrases = [(i, phrase) for i, phrase in enumerate(phrases) 
                                  if not re.match(punctuation_pattern, phrase)]
            
            # ボタン行を複数作成
            if selectable_phrases:
                # 行ごとに分割
                rows = [selectable_phrases[i:i+4] for i in range(0, len(selectable_phrases), 4)]
                
                for row in rows:
                    cols = st.columns(len(row))
                    for col_idx, (phrase_idx, phrase_text) in enumerate(row):
                        with cols[col_idx]:
                            is_selected = phrase_idx in st.session_state.selected_indices
                            btn_label = f"✓ {phrase_text}" if is_selected else phrase_text
                            btn_type = "primary" if is_selected else "secondary"
                            if st.button(btn_label, key=f"toggle_{phrase_idx}", type=btn_type, use_container_width=True):
                                toggle_phrase(phrase_idx)
                                st.rerun()
            
            # 選択状態を取得
            selected = st.session_state.selected_indices.copy()

            
            # プレビュー表示（隣接する選択ブロックは1つの穴埋めとして結合）
            if selected:
                # 隣接する選択を結合してプレビュー生成
                preview_parts = []
                answer_groups = []  # 結合された答えのグループ
                current_answer_group = []
                
                for i, phrase in enumerate(phrases):
                    if i in selected:
                        # 選択されたブロック
                        if not current_answer_group:
                            # 新しい穴埋めグループ開始
                            preview_parts.append("______")
                        current_answer_group.append(phrase)
                    else:
                        # 選択されていないブロック
                        if current_answer_group:
                            # 穴埋めグループ終了
                            answer_groups.append("".join(current_answer_group))
                            current_answer_group = []
                        preview_parts.append(phrase)
                
                # 最後のグループを処理
                if current_answer_group:
                    answer_groups.append("".join(current_answer_group))
                
                st.markdown("**プレビュー:**")
                st.info(''.join(preview_parts))
                st.markdown(f"**穴埋め箇所: {len(answer_groups)}個** (隣接ブロックは自動結合)")
                for idx, ans in enumerate(answer_groups, 1):
                    st.markdown(f"  {idx}. {ans}")
            
            # カード生成ボタン
            if st.button("✨ カード生成", type="primary", key="generate_cards_btn"):
                if not selected:
                    st.warning("穴埋め箇所を1つ以上選択してください。")
                else:
                    cards = generate_cards_from_selection(phrases, selected)
                    if cards:
                        st.session_state.generated_cards = cards
                        st.success(f"{len(cards)} 枚のカードを生成しました！")
                    else:
                        st.error("カードの生成に失敗しました。")

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
                        # 原文カードを先に保存
                        original_text = st.session_state.add_card_text if "add_card_text" in st.session_state else ""
                        source_id = None
                        if original_text:
                            source_id = add_source_card(user_id, original_text, title=card_title, category=selected_category)
                        
                        # 穴埋めカードを保存
                        count = 0
                        blank_count = len(cards_to_save)  # 穴埋め箇所の数
                        for card in cards_to_save:
                            if card['question'] and card['answer']:
                                add_card(user_id, card['question'], card['answer'], 
                                        title=card_title, category=selected_category,
                                        source_id=source_id, blank_count=blank_count)
                                count += 1
                        
                        st.success(f"{count} 枚のカードを保存しました！（原文カードも保存済み）")
                        # 全ての工程をクリア
                        if "phrases" in st.session_state:
                            del st.session_state.phrases
                        if "selected_indices" in st.session_state:
                            del st.session_state.selected_indices
                        if "generated_cards" in st.session_state:
                            del st.session_state.generated_cards
                        # 入力フィールドもクリア
                        st.session_state.add_card_category = ""
                        st.session_state.add_card_title = ""
                        st.session_state.add_card_text = ""
                        # ウィジェットをリセットするためカウンター増加
                        st.session_state.widget_key_counter += 1
                        st.rerun()


    # Manage Cards Page
    with tab3:
        st.title("🗂️ カード管理")
        
        cards = load_cards(user_id)
        source_cards = load_source_cards(user_id)
        CATEGORIES = ["民法", "商法", "刑法", "憲法", "行政法", "民事訴訟法", "刑事訴訟法", "その他"]
        
        if not source_cards and not cards:
            st.info("まだカードがありません。「カードを追加」メニューから作成してください。")
        else:
            # 統計表示
            st.markdown(f"**原文カード: {len(source_cards)} 件 / 暗記カード: {len(cards)} 枚**")
            
            # 検索ボックス
            search_query = st.text_input("🔍 検索", placeholder="原文、問題、答えで検索...", key="unified_search")
            
            # カテゴリタブ
            tabs = st.tabs(CATEGORIES)
            
            for i, category in enumerate(CATEGORIES):
                with tabs[i]:
                    # このカテゴリの原文カードをフィルタ
                    category_sources = [s for s in source_cards if s.get("category", "その他") == category]
                    
                    # 検索フィルタ
                    if search_query:
                        category_sources = [s for s in category_sources 
                                           if search_query.lower() in s.get('source_text', '').lower() 
                                           or search_query.lower() in s.get('title', '').lower()]
                    
                    # 原文を持たない孤立した暗記カード
                    orphan_cards = [c for c in cards 
                                   if c.get("category", "その他") == category 
                                   and not c.get("source_id")]
                    if search_query:
                        orphan_cards = [c for c in orphan_cards
                                       if search_query.lower() in c['question'].lower()
                                       or search_query.lower() in c['answer'].lower()]
                    
                    if not category_sources and not orphan_cards:
                        st.info(f"{category} のカードはありません。")
                    else:
                        # 原文カードごとに表示
                        for sc in category_sources:
                            source_id = sc['id']
                            source_title = sc.get('title', '無題')
                            source_text = sc.get('source_text', '')
                            
                            # この原文に紐づく暗記カード
                            linked_cards = [c for c in cards if c.get('source_id') == source_id]
                            
                            # Expander: 原文カード（紐づきカード数も表示）
                            with st.expander(f"📄 {source_title}（暗記カード {len(linked_cards)} 枚）", expanded=False):
                                
                                # 原文表示・編集
                                st.markdown("**📝 原文**")
                                edited_source = st.text_area(
                                    "", value=source_text, height=120, 
                                    key=f"edit_source_{source_id}"
                                )
                                
                                # 原文が変更されたか検出
                                source_modified = edited_source != source_text
                                
                                # 紐づき暗記カード
                                if linked_cards:
                                    st.markdown("---")
                                    st.markdown("**🎴 紐づき暗記カード**")
                                    
                                    cards_modified = False
                                    for j, card in enumerate(linked_cards):
                                        col1, col2, col3 = st.columns([5, 5, 1])
                                        with col1:
                                            new_q = st.text_input(f"問題 {j+1}", value=card['question'], key=f"q_{card['id']}")
                                        with col2:
                                            new_a = st.text_input(f"答え {j+1}", value=card['answer'], key=f"a_{card['id']}")
                                        with col3:
                                            st.markdown("")  # スペーサー
                                            if st.button("🗑️", key=f"del_single_{card['id']}", help="このカードのみ削除"):
                                                delete_card(user_id, card['id'])
                                                st.success("カードを削除しました")
                                                st.rerun()
                                        
                                        if new_q != card['question'] or new_a != card['answer']:
                                            cards_modified = True
                                    
                                    # 警告: 原文が変更されているのに暗記カードが変更されていない
                                    if source_modified and not cards_modified:
                                        st.warning("⚠️ 原文が変更されていますが、暗記カードが更新されていません。")
                                
                                # 操作ボタン
                                st.markdown("---")
                                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
                                
                                with btn_col1:
                                    if st.button("💾 保存", key=f"save_source_{source_id}", type="primary"):
                                        # 原文更新（簡易実装：削除→再作成はせず、今回はそのまま）
                                        # TODO: update_source_card関数が必要な場合は追加
                                        
                                        # 暗記カード更新
                                        updated_count = 0
                                        for card in linked_cards:
                                            new_q = st.session_state.get(f"q_{card['id']}", card['question'])
                                            new_a = st.session_state.get(f"a_{card['id']}", card['answer'])
                                            if new_q != card['question'] or new_a != card['answer']:
                                                update_card_content(user_id, card['id'], new_q, new_a, card.get('title', ''), card.get('category', 'その他'))
                                                updated_count += 1
                                        
                                        if updated_count > 0:
                                            st.success(f"✅ {updated_count}枚のカードを更新しました")
                                        else:
                                            st.info("変更はありませんでした")
                                        st.rerun()
                                
                                with btn_col2:
                                    if st.button("🗑️ 全削除", key=f"del_all_{source_id}"):
                                        st.session_state[f"confirm_del_all_{source_id}"] = True
                                
                                if st.session_state.get(f"confirm_del_all_{source_id}", False):
                                    st.warning("⚠️ この原文カードと紐づく暗記カードを全て削除しますか？")
                                    c1, c2, c3 = st.columns([1, 1, 3])
                                    with c1:
                                        if st.button("✓ 削除", key=f"yes_del_all_{source_id}", type="primary"):
                                            # 暗記カード削除
                                            for card in linked_cards:
                                                delete_card(user_id, card['id'])
                                            # 原文カード削除
                                            delete_source_card(user_id, source_id)
                                            del st.session_state[f"confirm_del_all_{source_id}"]
                                            st.success("削除しました")
                                            st.rerun()
                                    with c2:
                                        if st.button("✗ 戻る", key=f"no_del_all_{source_id}"):
                                            del st.session_state[f"confirm_del_all_{source_id}"]
                                            st.rerun()
                        
                        # 孤立した暗記カード（原文なし）
                        if orphan_cards:
                            st.markdown("---")
                            st.markdown("**� 原文なしの暗記カード**")
                            
                            for card in orphan_cards:
                                with st.expander(f"🎴 {card.get('title', '無題')}: {card['question'][:30]}..."):
                                    with st.form(key=f"orphan_form_{card['id']}"):
                                        new_q = st.text_input("問題", value=card['question'])
                                        new_a = st.text_input("答え", value=card['answer'])
                                        new_cat = st.selectbox("カテゴリ", CATEGORIES, index=CATEGORIES.index(card.get("category", "その他")))
                                        
                                        if st.form_submit_button("✓ 更新"):
                                            update_card_content(user_id, card['id'], new_q, new_a, card.get('title', ''), new_cat)
                                            st.success("更新しました")
                                            st.rerun()
                                    
                                    if st.button("🗑️ 削除", key=f"del_orphan_{card['id']}"):
                                        delete_card(user_id, card['id'])
                                        st.success("削除しました")
                                        st.rerun()

# ============ アプリケーション実行 ============

if check_auth():
    show_main_app()
else:
    show_login_page()
