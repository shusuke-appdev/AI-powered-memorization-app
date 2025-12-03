import streamlit as st
import datetime
import os
from gemini_client import generate_flashcards
from storage import load_cards, add_card, update_card_progress, delete_card, update_card_content
from utils import calculate_next_review

# Page Config
st.set_page_config(
    page_title="AI 暗記カード",
    page_icon="🧠",
    layout="centered"
)

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
    
    /* Segmented Control Styling */
    .stSegmentedControl {
        margin-bottom: 20px;
    }
    
    .stSegmentedControl button {
        font-size: 1.2rem !important;
        padding: 10px 20px !important;
        height: auto !important;
    }
    
    div[data-testid="stSegmentedControl"] {
        transform: scale(2.0);
        transform-origin: center top;
        margin-bottom: 30px;
    }

</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🧠 AI 暗記カード")
    
    # Check environment variable
    env_api_key = os.environ.get("GEMINI_API_KEY")
    if env_api_key:
        api_key = env_api_key
        st.success("✅ APIキーを環境変数から読み込みました")
    else:
        api_key = st.text_input("Gemini APIキー", type="password", help="Google GeminiのAPIキーを入力してください")
    
    st.markdown("---")
    st.markdown("Powered by Gemini 2.5 Flash (via API)")

# Top Navigation (Pill Style)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    page = st.segmented_control("メニュー", ["復習する", "カードを追加", "カード管理"], default="復習する", label_visibility="collapsed")

if page is None:
    page = "復習する"

# Add Cards Page
if page == "カードを追加":
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
            st.error("サイドバーにGemini APIキーを入力してください。")
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
                            add_card(card['question'], card['answer'], title=card_title, category=selected_category)
                            count += 1
                    st.success(f"{count} 枚のカードを保存しました！")
                    del st.session_state.generated_cards
                    st.rerun()

# Review Page
elif page == "復習する":
    st.title("📚 復習セッション")
    
    cards = load_cards()
    today = datetime.date.today().isoformat()
    
    # Filter cards due for review
    due_cards = [c for c in cards if c['next_review'] <= today]
    
    if not due_cards:
        # st.balloons() # Removed per user request
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
                update_card_progress(current_card['id'], new_stats)
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

# Manage Cards Page
elif page == "カード管理":
    st.title("🗂️ カード管理")
    
    cards = load_cards()
    CATEGORIES = ["民法", "商法", "刑法", "憲法", "行政法", "民事訴訟法", "刑事訴訟法", "その他"]
    
    if not cards:
        st.info("まだカードがありません。「カードを追加」メニューから作成してください。")
    else:
        st.markdown(f"**登録済みカード: {len(cards)} 枚**")
        
        # Group cards by category
        tabs = st.tabs(CATEGORIES)
        
        for i, category in enumerate(CATEGORIES):
            with tabs[i]:
                category_cards = [c for c in cards if c.get("category", "その他") == category]
                
                if not category_cards:
                    st.info(f"{category} のカードはありません。")
                else:
                    for j, card in enumerate(category_cards):
                        with st.expander(f"カード {j+1}: {card['question'][:20]}..."):
                            with st.form(key=f"edit_form_{card['id']}"):
                                new_category = st.selectbox("カテゴリ", CATEGORIES, index=CATEGORIES.index(card.get("category", "その他")))
                                new_title = st.text_input("タイトル", value=card.get('title', ''))
                                new_q = st.text_input("問題", value=card['question'])
                                new_a = st.text_input("答え", value=card['answer'])
                                
                                col1, col2 = st.columns([1, 4])
                                with col1:
                                    update_btn = st.form_submit_button("更新", type="primary")
                                with col2:
                                    delete_check = st.checkbox("このカードを削除する", key=f"del_{card['id']}")
                                
                                if update_btn:
                                    if delete_check:
                                        delete_card(card['id'])
                                        st.success("カードを削除しました")
                                        st.rerun()
                                    else:
                                        update_card_content(card['id'], new_q, new_a, new_title, new_category)
                                        st.success("カードを更新しました")
                                        st.rerun()
