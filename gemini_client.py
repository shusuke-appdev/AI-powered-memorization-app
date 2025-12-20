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
        
        model = genai.GenerativeModel("gemini-3-flash-preview")
        
        prompt = f"""以下のテキストを、暗記カード用の意味のまとまりに分割してください。

【文法的ルール】
1. 助詞（は、が、を、に、で、の、と、から、まで、より、へ等）は全て独立したブロックとして分割する
2. 句読点（。、）は独立したブロックとして分割する
3. 名詞句のまとまり:
   - 形容詞・形容動詞・連体詞 + 名詞 → 1ブロック（例: 「重大な過失」「不法な行為」「大きな損害」）
   - 名詞 + 名詞（複合語）→ 1ブロック（例: 「損害賠償請求権」「不法行為責任」）
   - ただし「名詞＋の＋名詞」は「名詞」「の」「名詞」と分割する
4. 動詞句のまとまり:
   - 副詞 + 動詞/形容詞 → 1ブロック（例: 「直ちに履行する」「著しく困難な」）
   - 動詞 + 補助動詞 → 1ブロック（例: 「することができる」「認められる」「なされなければならない」）
   - 動詞の活用語尾は動詞に含める
5. 格助詞相当の表現（による、として、に対して、において等）は独立したブロックとして分割する
6. 専門用語・法律用語・固有名詞は分割しない

【例1】
入力: 「重大な過失による不法行為は、損害賠償の対象となる。」
出力: ["重大な過失", "による", "不法行為", "は", "、", "損害賠償", "の", "対象", "と", "なる", "。"]

【例2】
入力: 「この点について、実行行為は構成要件的結果発生の現実的危険性を有する行為であり、かかる危険性は不作為によっても惹起されうるから、不作為も実行行為足りうる。」
出力: ["この点について", "、", "実行行為", "は", "構成要件的結果発生", "の", "現実的危険性", "を", "有する", "行為", "であり", "、", "かかる危険性", "は", "不作為", "によって", "も", "惹起されうる", "から", "、", "不作為", "も", "実行行為", "足りうる", "。"]

【例3】
入力: 「もっとも、自由保障の観点から、処罰範囲を限定すべきである。」
出力: ["もっとも", "、", "自由保障", "の", "観点", "から", "、", "処罰範囲", "を", "限定すべき", "である", "。"]

【例4】
入力: 「そこで、作為との構成要件的同価値性が認められる場合、すなわち、法的作為義務があったのにそれに違背し、作為が可能かつ容易であったのに作為をしなかった場合に限り、不作為にも実行行為性が認められると解する。」
出力: ["そこで", "、", "作為", "との", "構成要件的同価値性", "が", "認められる", "場合", "、", "すなわち", "、", "法的作為義務", "が", "あった", "のに", "それ", "に", "違背し", "、", "作為", "が", "可能", "かつ", "容易", "であった", "のに", "作為", "を", "しなかった", "場合", "に", "限り", "、", "不作為", "にも", "実行行為性", "が", "認められる", "と", "解する", "。"]

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
        
        model = genai.GenerativeModel("gemini-3-flash-preview")
        
        # 句読点のセット（穴埋め対象外）
        punctuation_set = {'。', '、', '，', '．', ',', '.', '！', '？', '!', '?', '：', ':', '；', ';'}
        
        # 文節にインデックスを付ける（句読点は除外して表示）
        indexed_phrases = []
        valid_indices = []
        for i, p in enumerate(phrases):
            if p.strip() not in punctuation_set:
                indexed_phrases.append(f"{i}: {p}")
                valid_indices.append(i)
        
        prompt = f"""以下の文節リストから、暗記カードの穴埋めにすべき重要な文節を選んでください。

【文節リスト】
{chr(10).join(indexed_phrases)}

【選び方の基準】
- 専門用語、固有名詞、数字、年号など、暗記すべき重要な情報を含む文節
- 全体の20-40%程度を選択
- 最低1つ、最大でリストの半分程度
- 句読点（。、等）は選択しないこと

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
        selected = result.get("selected_indices", [])
        
        # 句読点が含まれていた場合は除外
        selected = [i for i in selected if i in valid_indices]
        return selected
        
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
    
    if num_blanks <= 3:
        # 3箇所以下: 1枚のカード
        cards.append(build_card_from_groups(groups))
    else:
        # 4箇所以上: 穴埋め箇所数に応じてカード上限を設定
        # 上限 = 穴埋め箇所数 - 2、ただし最大5枚
        max_cards = min(num_blanks - 2, 5)
        
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
            if len(selected_combos) >= max_cards:
                break
        
        # 未カバーがあれば追加
        while covered != set(range(num_blanks)) and len(selected_combos) < max_cards:
            uncovered = set(range(num_blanks)) - covered
            for combo in shuffled_combos:
                if any(i in uncovered for i in combo):
                    if combo not in selected_combos:
                        selected_combos.append(combo)
                        covered.update(combo)
                        break
            else:
                break
        
        # 上限まで追加
        remaining = [c for c in shuffled_combos if c not in selected_combos]
        while len(selected_combos) < max_cards and remaining:
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
