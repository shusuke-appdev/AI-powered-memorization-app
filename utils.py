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
    repetitions = card_data.get("repetitions", 0)
    interval = card_data.get("interval", 0)
    ease_factor = card_data.get("ease_factor", 2.5)

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
        "repetitions": repetitions,
        "interval": interval,
        "ease_factor": ease_factor,
        "last_review": datetime.date.today().isoformat(),
        "next_review": next_review_date.isoformat(),
    }


def get_initial_card_state():
    """Returns the initial state for a new card."""
    return {
        "repetitions": 0,
        "interval": 0,
        "ease_factor": 2.5,
        "last_review": None,
        "next_review": datetime.date.today().isoformat(),  # Available immediately
    }


# ============ ハイブリッド最適化アルゴリズム ============


def select_hybrid_quota(due_cards, limit, all_cards):
    """
    ハイブリッド最適化によるカード選択（ランク対応・知識類型カード比率調整版）

    1. 同一source_idのカードを除外（1日1枚まで）
    2. 知識・類型カードは全体の1/5を割り当て
    3. 各グループごとに、ランク（重要度）と苦手/期限を組み合わせて選出
    4. ランクA+は優先的に出題（出題頻度を高める）
    """
    if not due_cards:
        return []

    # ランクの重み（数値が大きいほど優先的に出題）
    RANK_WEIGHT = {"A+": 5, "A": 4, "B+": 3, "B": 2, "C": 1}

    # 1. 同一source_idのカードを除外
    seen_source_ids = set()
    unique_cards = []
    for card in due_cards:
        source_id = card.get("source_id")
        if source_id is None:
            unique_cards.append(card)
        elif source_id not in seen_source_ids:
            seen_source_ids.add(source_id)
            unique_cards.append(card)

    if len(unique_cards) <= limit:
        return unique_cards

    # 2. 知識・類型カードと一般カードに分類
    tk_cards = []
    normal_cards = []
    for c in unique_cards:
        is_tk = c.get("category") in ["知識", "類型"] or c.get("card_type") in ["知識", "類型"]
        if is_tk:
            tk_cards.append(c)
        else:
            normal_cards.append(c)

    # 知識・類型カードの目標採用数 (1/5)
    target_tk_count = limit // 5
    actual_tk_count = min(target_tk_count, len(tk_cards))
    actual_normal_count = min(limit - actual_tk_count, len(normal_cards))
    
    # normal_cardsが足りない場合はtk_cardsで補填
    if actual_tk_count + actual_normal_count < limit:
        actual_tk_count = min(len(tk_cards), limit - actual_normal_count)

    def select_group_cards(candidates, count):
        if not candidates or count == 0:
            return []
        if len(candidates) <= count:
            return candidates

        diff_count = (count + 1) // 2
        dead_count = count - diff_count

        # 苦手優先：ランクが高く、かつease_factorが低いものを優先
        # ランクの重みをマイナスにして降順（大きい順）と同等にし、次はease_factorの昇順
        difficulty_sorted = sorted(
            candidates,
            key=lambda c: (
                -RANK_WEIGHT.get(c.get("rank", "B"), 2),
                c.get("ease_factor", 2.5)
            )
        )
        difficulty_cards = difficulty_sorted[:diff_count]

        # 期限優先：ランクが高く、かつnext_reviewが古いものを優先
        remaining = [c for c in candidates if c not in difficulty_cards]
        deadline_sorted = sorted(
            remaining,
            key=lambda c: (
                -RANK_WEIGHT.get(c.get("rank", "B"), 2),
                c.get("next_review", "9999-99-99")
            )
        )
        deadline_cards = deadline_sorted[:dead_count]

        return difficulty_cards + deadline_cards

    selected_tk = select_group_cards(tk_cards, actual_tk_count)
    selected_normal = select_group_cards(normal_cards, actual_normal_count)

    selected = selected_tk + selected_normal

    # 3. （オプション）総穴埋め数を目標値に調整
    if all_cards:
        avg_blank = sum(c.get("blank_count", 1) for c in all_cards) / len(all_cards)
        target_blanks = avg_blank * limit
        # 調整時も、知識・類型の比率を大きく崩さない範囲で行うことが望ましいが
        # 実装の簡略化のため現状のまま _adjust_to_target_blanks を通す
        selected = _adjust_to_target_blanks(
            selected, unique_cards, target_blanks, limit
        )

    return selected


def _adjust_to_target_blanks(selected, candidates, target, limit):
    """
    総穴埋め数を目標値に近づけるよう調整
    ※同一source_idのカードが選ばれないようチェック
    """
    current_blanks = sum(c.get("blank_count", 1) for c in selected)

    # 目標との差が小さい場合は調整不要
    if abs(current_blanks - target) < 1:
        return selected

    # 選ばれていないカードを取得
    not_selected = [c for c in candidates if c not in selected]

    # 現在選択中のsource_idセット（重複チェック用）
    def get_selected_source_ids(cards):
        return {c.get("source_id") for c in cards if c.get("source_id") is not None}

    # 入れ替え試行（最大5回）
    for _ in range(5):
        if abs(current_blanks - target) < 1:
            break

        selected_source_ids = get_selected_source_ids(selected)

        if current_blanks > target:
            # 穴埋めが多いカードを少ないカードに入れ替え
            high_blank_cards = sorted(
                selected, key=lambda c: c.get("blank_count", 1), reverse=True
            )
            low_blank_candidates = sorted(
                not_selected, key=lambda c: c.get("blank_count", 1)
            )

            for high_card in high_blank_cards:
                for low_card in low_blank_candidates:
                    low_card_source_id = low_card.get("source_id")
                    # 入れ替え対象のsource_idが既に選択済みならスキップ
                    if (
                        low_card_source_id is not None
                        and low_card_source_id in selected_source_ids
                    ):
                        if low_card_source_id != high_card.get("source_id"):
                            continue  # 異なるsource_idが既に存在 → スキップ

                    if low_card.get("blank_count", 1) < high_card.get("blank_count", 1):
                        # 入れ替え
                        selected = [c for c in selected if c != high_card] + [low_card]
                        not_selected = [c for c in not_selected if c != low_card] + [
                            high_card
                        ]
                        current_blanks = sum(c.get("blank_count", 1) for c in selected)
                        break
                if abs(current_blanks - target) < 1:
                    break
        else:
            # 穴埋めが少ないカードを多いカードに入れ替え
            low_blank_cards = sorted(selected, key=lambda c: c.get("blank_count", 1))
            high_blank_candidates = sorted(
                not_selected, key=lambda c: c.get("blank_count", 1), reverse=True
            )

            for low_card in low_blank_cards:
                for high_card in high_blank_candidates:
                    high_card_source_id = high_card.get("source_id")
                    # 入れ替え対象のsource_idが既に選択済みならスキップ
                    if (
                        high_card_source_id is not None
                        and high_card_source_id in selected_source_ids
                    ):
                        if high_card_source_id != low_card.get("source_id"):
                            continue  # 異なるsource_idが既に存在 → スキップ

                    if high_card.get("blank_count", 1) > low_card.get("blank_count", 1):
                        # 入れ替え
                        selected = [c for c in selected if c != low_card] + [high_card]
                        not_selected = [c for c in not_selected if c != high_card] + [
                            low_card
                        ]
                        current_blanks = sum(c.get("blank_count", 1) for c in selected)
                        break
                if abs(current_blanks - target) < 1:
                    break

    return selected[:limit]


# ============ カテゴリ別カラースキーム ============

# カテゴリ分類
CATEGORY_GROUPS = {
    "民事系": ["民法", "商法", "民事訴訟法"],
    "刑事系": ["刑法", "刑事訴訟法"],
    "公法系": ["憲法", "行政法"],
    "その他": ["その他"],
}

# カラーパレット（ライトモード / ダークモード）
CATEGORY_COLORS = {
    "民事系": {
        "light": {"bg": "#fecaca", "text": "#b91c1c", "border": "#fca5a5"},
        "dark": {"bg": "#7f1d1d", "text": "#fca5a5", "border": "#991b1b"},
    },
    "刑事系": {
        "light": {"bg": "#bfdbfe", "text": "#1d4ed8", "border": "#93c5fd"},
        "dark": {"bg": "#1e3a5f", "text": "#93c5fd", "border": "#1e40af"},
    },
    "公法系": {
        "light": {"bg": "#bbf7d0", "text": "#15803d", "border": "#86efac"},
        "dark": {"bg": "#14532d", "text": "#86efac", "border": "#166534"},
    },
    "その他": {
        "light": {"bg": "#fef08a", "text": "#a16207", "border": "#fde047"},
        "dark": {"bg": "#713f12", "text": "#fde047", "border": "#854d0e"},
    },
}


def get_category_group(category):
    """科目名からカテゴリグループを取得"""
    for group, subjects in CATEGORY_GROUPS.items():
        if category in subjects:
            return group
    return "その他"


def get_category_colors(category, is_dark_mode=False):
    """
    カテゴリ名から色情報を取得

    Args:
        category: 科目名（例: "民法", "刑法"）
        is_dark_mode: ダークモードかどうか

    Returns:
        dict: {"bg": 背景色, "text": 文字色, "border": ボーダー色}
    """
    group = get_category_group(category)
    mode = "dark" if is_dark_mode else "light"
    return CATEGORY_COLORS.get(group, CATEGORY_COLORS["その他"])[mode]


def get_all_category_css():
    """全カテゴリのCSSクラスを生成"""
    css_rules = []

    for group, colors in CATEGORY_COLORS.items():
        subjects = CATEGORY_GROUPS.get(group, [group])
        for subject in subjects:
            # ライトモード
            css_rules.append(f"""
    .category-{subject} {{
        background-color: {colors["light"]["bg"]} !important;
        color: {colors["light"]["text"]} !important;
        border: 1px solid {colors["light"]["border"]} !important;
    }}
""")

    # ダークモード
    css_rules.append("    /* ダークモード用カテゴリ色 */")
    for group, colors in CATEGORY_COLORS.items():
        subjects = CATEGORY_GROUPS.get(group, [group])
        for subject in subjects:
            css_rules.append(f"""
    .dark-mode .category-{subject} {{
        background-color: {colors["dark"]["bg"]} !important;
        color: {colors["dark"]["text"]} !important;
        border: 1px solid {colors["dark"]["border"]} !important;
    }}
""")

    return "\n".join(css_rules)
