"""
エクスポート/インポートモジュール
カードデータのバックアップと復元
"""
import json
import csv
import io
from datetime import date

def export_cards_json(cards, source_cards=None):
    """
    カードデータをJSON形式でエクスポート
    
    Args:
        cards: 暗記カードのリスト
        source_cards: 原文カードのリスト（オプション）
    
    Returns:
        str: JSON文字列
    """
    export_data = {
        "version": "1.0",
        "exported_at": date.today().isoformat(),
        "cards": cards,
        "source_cards": source_cards or []
    }
    return json.dumps(export_data, ensure_ascii=False, indent=2)

def export_cards_csv(cards):
    """
    カードデータをCSV形式でエクスポート
    
    Args:
        cards: 暗記カードのリスト
    
    Returns:
        str: CSV文字列
    """
    if not cards:
        return ""
    
    output = io.StringIO()
    fieldnames = ["title", "category", "question", "answer", "ease_factor", "interval", "repetitions", "next_review"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for card in cards:
        writer.writerow({
            "title": card.get("title", ""),
            "category": card.get("category", "その他"),
            "question": card.get("question", ""),
            "answer": card.get("answer", ""),
            "ease_factor": card.get("ease_factor", 2.5),
            "interval": card.get("interval", 1),
            "repetitions": card.get("repetitions", 0),
            "next_review": card.get("next_review", "")
        })
    
    return output.getvalue()

def import_cards_json(json_data, existing_cards=None, duplicate_action="skip"):
    """
    JSONからカードデータをインポート
    
    Args:
        json_data: JSON文字列
        existing_cards: 既存のカードリスト（重複チェック用）
        duplicate_action: 重複時の動作 ("skip" or "overwrite")
    
    Returns:
        dict: {
            "cards": インポートするカードのリスト,
            "source_cards": インポートする原文カードのリスト,
            "skipped": スキップした数,
            "error": エラーメッセージ（あれば）
        }
    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        return {"cards": [], "source_cards": [], "skipped": 0, "error": f"JSON解析エラー: {e}"}
    
    cards = data.get("cards", [])
    source_cards = data.get("source_cards", [])
    
    # 重複チェック
    skipped = 0
    if existing_cards and duplicate_action == "skip":
        existing_set = {(c.get("question", ""), c.get("answer", "")) for c in existing_cards}
        new_cards = []
        for card in cards:
            key = (card.get("question", ""), card.get("answer", ""))
            if key not in existing_set:
                new_cards.append(card)
            else:
                skipped += 1
        cards = new_cards
    
    return {
        "cards": cards,
        "source_cards": source_cards,
        "skipped": skipped,
        "error": None
    }

def import_cards_csv(csv_data, existing_cards=None, duplicate_action="skip", reset_progress=True):
    """
    CSVからカードデータをインポート
    
    Args:
        csv_data: CSV文字列
        existing_cards: 既存のカードリスト（重複チェック用）
        duplicate_action: 重複時の動作 ("skip" or "overwrite")
        reset_progress: 学習進捗をリセットするか
    
    Returns:
        dict: {
            "cards": インポートするカードのリスト,
            "skipped": スキップした数,
            "error": エラーメッセージ（あれば）
        }
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_data))
        cards = []
        
        for row in reader:
            card = {
                "title": row.get("title", ""),
                "category": row.get("category", "その他"),
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
            }
            
            if reset_progress:
                card["ease_factor"] = 2.5
                card["interval"] = 1
                card["repetitions"] = 0
                card["next_review"] = date.today().isoformat()
            else:
                card["ease_factor"] = float(row.get("ease_factor", 2.5))
                card["interval"] = int(row.get("interval", 1))
                card["repetitions"] = int(row.get("repetitions", 0))
                card["next_review"] = row.get("next_review", date.today().isoformat())
            
            if card["question"] and card["answer"]:
                cards.append(card)
        
    except Exception as e:
        return {"cards": [], "skipped": 0, "error": f"CSV解析エラー: {e}"}
    
    # 重複チェック
    skipped = 0
    if existing_cards and duplicate_action == "skip":
        existing_set = {(c.get("question", ""), c.get("answer", "")) for c in existing_cards}
        new_cards = []
        for card in cards:
            key = (card["question"], card["answer"])
            if key not in existing_set:
                new_cards.append(card)
            else:
                skipped += 1
        cards = new_cards
    
    return {
        "cards": cards,
        "skipped": skipped,
        "error": None
    }

def render_export_import_ui(user_id, cards, source_cards, st_module, add_card_func, add_source_card_func):
    """
    エクスポート/インポートのUIを表示
    
    Args:
        user_id: ユーザーID
        cards: 現在のカードリスト
        source_cards: 現在の原文カードリスト
        st_module: streamlitモジュール
        add_card_func: カード追加関数
        add_source_card_func: 原文カード追加関数
    """
    st = st_module
    
    st.markdown("### 📦 データ管理")
    
    export_tab, import_tab = st.tabs(["📥 エクスポート", "📤 インポート"])
    
    with export_tab:
        st.markdown("カードデータをダウンロードしてバックアップできます。")
        
        col1, col2 = st.columns(2)
        with col1:
            # JSONエクスポート
            json_data = export_cards_json(cards, source_cards)
            st.download_button(
                label="📥 JSONでダウンロード",
                data=json_data,
                file_name=f"flashcards_{date.today().isoformat()}.json",
                mime="application/json",
                use_container_width=True
            )
        with col2:
            # CSVエクスポート
            csv_data = export_cards_csv(cards)
            st.download_button(
                label="📥 CSVでダウンロード",
                data=csv_data,
                file_name=f"flashcards_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.info(f"📊 カード数: {len(cards)}枚 / 原文カード: {len(source_cards)}件")
    
    with import_tab:
        st.markdown("バックアップファイルからカードを復元できます。")
        
        uploaded_file = st.file_uploader(
            "ファイルを選択",
            type=["json", "csv"],
            key="import_file_uploader"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            duplicate_action = st.radio(
                "重複時の処理",
                ["skip", "overwrite"],
                format_func=lambda x: "スキップ" if x == "skip" else "上書き",
                horizontal=True,
                key="import_duplicate_action"
            )
        with col2:
            reset_progress = st.checkbox(
                "学習進捗をリセット",
                value=True,
                key="import_reset_progress"
            )
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode("utf-8")
            file_type = uploaded_file.name.split(".")[-1].lower()
            
            if st.button("📤 インポート実行", type="primary", use_container_width=True):
                if file_type == "json":
                    result = import_cards_json(file_content, cards, duplicate_action)
                else:
                    result = import_cards_csv(file_content, cards, duplicate_action, reset_progress)
                
                if result["error"]:
                    st.error(result["error"])
                else:
                    imported_count = 0
                    for card in result["cards"]:
                        add_card_func(
                            user_id,
                            card["question"],
                            card["answer"],
                            title=card.get("title", ""),
                            category=card.get("category", "その他")
                        )
                        imported_count += 1
                    
                    # 原文カードもインポート（JSONの場合）
                    source_imported = 0
                    if file_type == "json" and result.get("source_cards"):
                        for sc in result["source_cards"]:
                            add_source_card_func(
                                user_id,
                                sc.get("source_text", ""),
                                title=sc.get("title", ""),
                                category=sc.get("category", "その他")
                            )
                            source_imported += 1
                    
                    st.success(f"✅ {imported_count}枚のカードをインポートしました！")
                    if result["skipped"] > 0:
                        st.info(f"📋 {result['skipped']}枚の重複カードをスキップしました。")
                    if source_imported > 0:
                        st.info(f"📄 {source_imported}件の原文カードもインポートしました。")
                    st.rerun()
