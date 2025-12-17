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
        
        prompt = f"""以下のテキストを、暗記カード用の意味のまとまりに分割してください。

【文法的ルール】
1. 形容詞・連体詞は修飾する名詞と同じブロックにする（例: 「重大な過失」「不法な行為」）
2. 副詞は修飾する動詞・形容詞と同じブロックにする
3. 助詞（は、が、を、に、で、の、と、から、まで等）は独立したブロックとして分割する
4. 専門用語・固有名詞・法律用語は1つのブロックとして保持する
5. 句読点（。、）の前後は必ずブロックを分ける（句読点は独立したブロック）
6. 細かく分割することを優先する

【例】
入力: 「重大な過失による不法行為は、損害賠償の対象となる。」
出力: ["重大な過失", "による", "不法行為", "は", "、", "損害賠償", "の", "対象", "と", "なる", "。"]

【テキスト】
{text}

【出力形式】
{{"phrases": ["ブロック1", "ブロック2", "。", ...]}}"""
        
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

def merge_adjacent_selections(phrases, selected_indices):
    """
    隣接する選択インデックスをグループ化
    
    Returns:
        list of lists: 隣接するインデックスのグループ [[0,1,2], [5,6], ...]
    """
    if not selected_indices:
        return []
    
    sorted_indices = sorted(selected_indices)
    groups = []
    current_group = [sorted_indices[0]]
    
    for i in range(1, len(sorted_indices)):
        # 隣接しているか、間に句読点のみがあるかチェック
        prev_idx = sorted_indices[i-1]
        curr_idx = sorted_indices[i]
        
        # 間にあるフレーズをチェック
        is_adjacent = True
        for j in range(prev_idx + 1, curr_idx):
            # 句読点以外があれば隣接とみなさない
            if not phrases[j].strip() in ['。', '、', '，', '．', ',', '.', '']:
                is_adjacent = False
                break
        
        if is_adjacent and curr_idx == prev_idx + 1:
            # 完全に隣接
            current_group.append(curr_idx)
        elif is_adjacent:
            # 間に句読点のみ
            current_group.append(curr_idx)
        else:
            # 隣接していない
            groups.append(current_group)
            current_group = [curr_idx]
    
    groups.append(current_group)
    return groups

def generate_cards_from_selection(phrases, selected_indices):
    """
    選択された文節を穴埋めにしてカードを生成（隣接ブロックは結合）
    
    Args:
        phrases (list): 文節のリスト
        selected_indices (list): 穴埋めにする文節のインデックス
        
    Returns:
        list: カードのリスト
    """
    if not selected_indices:
        return []
    
    # 隣接する選択をグループ化
    groups = merge_adjacent_selections(phrases, selected_indices)
    num_blanks = len(groups)  # 結合後の穴埋め箇所数
    
    cards = []
    
    def build_card_from_groups(target_groups):
        """指定されたグループを穴埋めにしてカードを作成"""
        question_parts = []
        answers = []
        all_target_indices = set()
        for g in target_groups:
            all_target_indices.update(g)
        
        current_answer = []
        in_blank = False
        
        for i, phrase in enumerate(phrases):
            if i in all_target_indices:
                if not in_blank:
                    question_parts.append('______')
                    in_blank = True
                current_answer.append(phrase)
            else:
                if in_blank and current_answer:
                    answers.append(''.join(current_answer))
                    current_answer = []
                    in_blank = False
                question_parts.append(phrase)
        
        if current_answer:
            answers.append(''.join(current_answer))
        
        return {
            "question": ''.join(question_parts),
            "answer": " / ".join(answers)
        }
    
    if num_blanks <= 2:
        # 2箇所以下: 1枚のカード
        cards.append(build_card_from_groups(groups))
    else:
        # 3箇所以上: 組み合わせから選択
        all_combos = list(combinations(range(len(groups)), min(3, num_blanks)))
        
        selected_combos = []
        covered = set()
        
        shuffled_combos = all_combos.copy()
        random.shuffle(shuffled_combos)
        
        # 全ての穴埋め箇所をカバー
        for combo in shuffled_combos:
            if covered == set(range(num_blanks)):
                break
            new_coverage = set(combo) - covered
            if new_coverage:
                selected_combos.append(combo)
                covered.update(combo)
            if len(selected_combos) >= 10:
                break
        
        # 未カバーがあれば追加
        while covered != set(range(num_blanks)) and len(selected_combos) < 10:
            uncovered = set(range(num_blanks)) - covered
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
            target_groups = [groups[i] for i in combo]
            cards.append(build_card_from_groups(target_groups))
    
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
