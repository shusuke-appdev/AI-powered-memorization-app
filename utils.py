import datetime

def calculate_next_review(quality, card_data):
    """
    Calculates the next review date using the SuperMemo-2 (SM-2) algorithm.

    Args:
        quality (int): The quality of the response (0-5).
                       0: Complete blackout.
                       1: Incorrect response; the correct one remembered.
                       2: Incorrect response; where the correct one seemed easy to recall.
                       3: Correct response recalled with serious difficulty.
                       4: Correct response after a hesitation.
                       5: Perfect recall.
        card_data (dict): Dictionary containing current card status:
                          - repetitions (int): Number of consecutive correct recalls.
                          - interval (int): Inter-repetition interval in days.
                          - ease_factor (float): E-Factor.
                          - last_review (str): ISO format date string.

    Returns:
        dict: Updated card data with new repetitions, interval, ease_factor, and next_review.
    """
    repetitions = card_data.get('repetitions', 0)
    interval = card_data.get('interval', 0)
    ease_factor = card_data.get('ease_factor', 2.5)

    if quality >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = int(interval * ease_factor)
        
        repetitions += 1
    else:
        repetitions = 0
        interval = 1
    
    # Update Ease Factor
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    # EF' cannot go below 1.3
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < 1.3:
        ease_factor = 1.3
    
    next_review_date = datetime.date.today() + datetime.timedelta(days=interval)

    return {
        'repetitions': repetitions,
        'interval': interval,
        'ease_factor': ease_factor,
        'last_review': datetime.date.today().isoformat(),
        'next_review': next_review_date.isoformat()
    }

def get_initial_card_state():
    """Returns the initial state for a new card."""
    return {
        'repetitions': 0,
        'interval': 0,
        'ease_factor': 2.5,
        'last_review': None,
        'next_review': datetime.date.today().isoformat() # Available immediately
    }

# ============ ハイブリッド最適化アルゴリズム ============

def select_hybrid_quota(due_cards, limit, all_cards):
    """
    ハイブリッド最適化によるカード選択
    
    1. 同一source_idのカードを除外（1日1枚まで）
    2. 前半(ceil): 苦手カード優先（低ease_factor順）
    3. 後半(floor): 期限優先（古いnext_review順）
    4. 総穴埋め数を目標値に調整
    
    Args:
        due_cards: 復習対象カードのリスト
        limit: 1日の上限枚数
        all_cards: 全カードリスト（平均blank_count計算用）
    
    Returns:
        選択されたカードのリスト
    """
    if not due_cards:
        return []
    
    # 1. 同一source_idのカードを除外（各source_idから1枚のみ）
    # ※カード数に関わらず常に適用
    seen_source_ids = set()
    unique_cards = []
    for card in due_cards:
        source_id = card.get('source_id')
        if source_id is None:
            # source_idがないカードはそのまま追加
            unique_cards.append(card)
        elif source_id not in seen_source_ids:
            seen_source_ids.add(source_id)
            unique_cards.append(card)
    
    if len(unique_cards) <= limit:
        return unique_cards
    
    # 2. ノルマを半分に分割（奇数時は苦手優先が多い）
    difficulty_count = (limit + 1) // 2
    deadline_count = limit - difficulty_count
    
    # 苦手カード優先（低ease_factor順）
    difficulty_sorted = sorted(unique_cards, key=lambda c: c.get('ease_factor', 2.5))
    difficulty_cards = difficulty_sorted[:difficulty_count]
    
    # 期限優先（古いnext_review順）- 苦手カードとして選ばれなかったものから
    remaining = [c for c in unique_cards if c not in difficulty_cards]
    deadline_sorted = sorted(remaining, key=lambda c: c.get('next_review', '9999-99-99'))
    deadline_cards = deadline_sorted[:deadline_count]
    
    selected = difficulty_cards + deadline_cards
    
    # 3. 総穴埋め数を目標値に調整
    if all_cards:
        avg_blank = sum(c.get('blank_count', 1) for c in all_cards) / len(all_cards)
        target_blanks = avg_blank * limit
        selected = _adjust_to_target_blanks(selected, unique_cards, target_blanks, limit)
    
    return selected

def _adjust_to_target_blanks(selected, candidates, target, limit):
    """
    総穴埋め数を目標値に近づけるよう調整
    """
    current_blanks = sum(c.get('blank_count', 1) for c in selected)
    
    # 目標との差が小さい場合は調整不要
    if abs(current_blanks - target) < 1:
        return selected
    
    # 選ばれていないカードを取得
    not_selected = [c for c in candidates if c not in selected]
    
    # 入れ替え試行（最大5回）
    for _ in range(5):
        if abs(current_blanks - target) < 1:
            break
        
        if current_blanks > target:
            # 穴埋めが多いカードを少ないカードに入れ替え
            high_blank_cards = sorted(selected, key=lambda c: c.get('blank_count', 1), reverse=True)
            low_blank_candidates = sorted(not_selected, key=lambda c: c.get('blank_count', 1))
            
            for high_card in high_blank_cards:
                for low_card in low_blank_candidates:
                    if low_card.get('blank_count', 1) < high_card.get('blank_count', 1):
                        # 入れ替え
                        selected = [c for c in selected if c != high_card] + [low_card]
                        not_selected = [c for c in not_selected if c != low_card] + [high_card]
                        current_blanks = sum(c.get('blank_count', 1) for c in selected)
                        break
                if abs(current_blanks - target) < 1:
                    break
        else:
            # 穴埋めが少ないカードを多いカードに入れ替え
            low_blank_cards = sorted(selected, key=lambda c: c.get('blank_count', 1))
            high_blank_candidates = sorted(not_selected, key=lambda c: c.get('blank_count', 1), reverse=True)
            
            for low_card in low_blank_cards:
                for high_card in high_blank_candidates:
                    if high_card.get('blank_count', 1) > low_card.get('blank_count', 1):
                        # 入れ替え
                        selected = [c for c in selected if c != low_card] + [high_card]
                        not_selected = [c for c in not_selected if c != high_card] + [low_card]
                        current_blanks = sum(c.get('blank_count', 1) for c in selected)
                        break
                if abs(current_blanks - target) < 1:
                    break
    
    return selected[:limit]
