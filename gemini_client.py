import re
import random
import json
from itertools import combinations

# ============ AI文節分割 ============

def split_into_phrases(text, api_key):
    """
    AIを使ってテキストを文節（意味のある単位）に分割
    
    Args:
        text (str): 分割するテキスト
        api_key (str): Gemini APIキー
        
    Returns:
        list: 文節のリスト
    """
    if not api_key:
        # APIキーがない場合は句読点で簡易分割
        return simple_split(text)
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""以下のテキストを、日本語の文節（意味のある最小単位）に分割してください。

【ルール】
1. 助詞や助動詞は前の語と一緒にする（例: 「民法は」「規定している」）
2. 専門用語や固有名詞は1つの単位として保持する
3. 句読点（。、，．,.）は単独の文節として分割する
4. 分割した文節をJSON配列で返す

【テキスト】
{text}

【出力形式】
{{"phrases": ["文節1", "文節2", "。", ...]}}"""
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                top_p=0.95,
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text)
        phrases = result.get("phrases", [])
        
        if phrases:
            return phrases
        else:
            return simple_split(text)
            
    except Exception as e:
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str or "limit" in error_str or "429" in error_str:
            return {"error": "API_QUOTA_EXCEEDED", "message": "APIの無料枠利用制限に達しました。しばらく待ってから再試行するか、別のAPIキーを使用してください。"}
        print(f"AI分割エラー: {e}")
        return simple_split(text)

def simple_split(text):
    """句読点とスペースで簡易分割"""
    # 句読点の後で分割（句読点は前の部分に含める）
    parts = re.split(r'(?<=[。、，．,.])', text)
    result = []
    for part in parts:
        part = part.strip()
        if part:
            result.append(part)
    return result if result else [text]

# ============ AI穴埋め提案 ============

def suggest_blanks(phrases, api_key):
    """
    AIが穴埋めにすべき文節を提案
    
    Args:
        phrases (list): 文節のリスト
        api_key (str): Gemini APIキー
        
    Returns:
        list: 穴埋めにすべき文節のインデックスリスト
    """
    if not api_key:
        return []
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # 文節にインデックスを付ける
        indexed_phrases = [f"{i}: {p}" for i, p in enumerate(phrases)]
        
        prompt = f"""以下の文節リストから、暗記カードの穴埋めにすべき重要な文節を選んでください。

【文節リスト】
{chr(10).join(indexed_phrases)}

【選び方の基準】
- 専門用語、固有名詞、数字、年号など、暗記すべき重要な情報を含む文節
- 全体の20-40%程度を選択
- 最低1つ、最大でリストの半分程度

【出力形式】
{{"selected_indices": [0, 2, 5]}}  // 選んだ文節のインデックス番号"""
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                top_p=0.95,
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text)
        return result.get("selected_indices", [])
        
    except Exception as e:
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str or "limit" in error_str or "429" in error_str:
            return {"error": "API_QUOTA_EXCEEDED", "message": "APIの無料枠利用制限に達しました。"}
        print(f"AI提案エラー: {e}")
        return []

# ============ カード生成 ============

def generate_cards_from_selection(phrases, selected_indices):
    """
    選択された文節を穴埋めにしてカードを生成
    
    Args:
        phrases (list): 文節のリスト
        selected_indices (list): 穴埋めにする文節のインデックス
        
    Returns:
        list: カードのリスト
    """
    if not selected_indices:
        return []
    
    cards = []
    num_blanks = len(selected_indices)
    
    if num_blanks <= 2:
        # 2箇所以下: 1枚のカード
        question_parts = []
        answers = []
        for i, phrase in enumerate(phrases):
            if i in selected_indices:
                question_parts.append('______')
                answers.append(phrase)
            else:
                question_parts.append(phrase)
        
        cards.append({
            "question": ''.join(question_parts),
            "answer": " / ".join(answers)
        })
    else:
        # 3箇所以上: 組み合わせから選択
        all_combos = list(combinations(selected_indices, min(3, num_blanks)))
        
        selected_combos = []
        covered = set()
        
        shuffled_combos = all_combos.copy()
        random.shuffle(shuffled_combos)
        
        # 全ての穴埋め箇所をカバー
        for combo in shuffled_combos:
            if covered == set(selected_indices):
                break
            new_coverage = set(combo) - covered
            if new_coverage:
                selected_combos.append(combo)
                covered.update(combo)
            if len(selected_combos) >= 10:
                break
        
        # 未カバーがあれば追加
        while covered != set(selected_indices) and len(selected_combos) < 10:
            uncovered = set(selected_indices) - covered
            for combo in shuffled_combos:
                if any(i in uncovered for i in combo):
                    if combo not in selected_combos:
                        selected_combos.append(combo)
                        covered.update(combo)
                        break
            else:
                break
        
        # 10枚まで追加
        remaining = [c for c in shuffled_combos if c not in selected_combos]
        while len(selected_combos) < 10 and remaining:
            selected_combos.append(remaining.pop(0))
        
        # カード生成
        for combo in selected_combos:
            question_parts = []
            answers = []
            for i, phrase in enumerate(phrases):
                if i in combo:
                    question_parts.append('______')
                    answers.append(phrase)
                else:
                    question_parts.append(phrase)
            
            cards.append({
                "question": ''.join(question_parts),
                "answer": " / ".join(answers)
            })
    
    return cards

# ============ 旧API互換 ============

def parse_blanks_from_text(text):
    """【】マーカーからカードを生成（旧方式との互換性のため残す）"""
    pattern = r'【(.+?)】'
    matches = list(re.finditer(pattern, text))
    
    if not matches:
        return []
    
    # 文節リストと選択インデックスに変換
    phrases = []
    selected_indices = []
    last_end = 0
    
    for i, m in enumerate(matches):
        # マッチ前のテキスト
        if m.start() > last_end:
            before = text[last_end:m.start()]
            if before:
                phrases.append(before)
        
        # マッチしたテキスト（穴埋め対象）
        selected_indices.append(len(phrases))
        phrases.append(m.group(1))
        last_end = m.end()
    
    # 最後のテキスト
    if last_end < len(text):
        after = text[last_end:]
        if after:
            phrases.append(after)
    
    return generate_cards_from_selection(phrases, selected_indices)

def validate_blank_markers(text):
    """穴埋め指定の検証（旧方式との互換性）"""
    pattern = r'【(.+?)】'
    matches = re.findall(pattern, text)
    
    if not matches:
        return False, "穴埋め箇所が指定されていません。", 0
    
    return True, f"{len(matches)}箇所の穴埋めが指定されています。", len(matches)

def generate_flashcards(text, api_key=None, keywords=None):
    """旧API互換のエントリーポイント"""
    is_valid, message, count = validate_blank_markers(text)
    if not is_valid:
        return None
    return parse_blanks_from_text(text)
