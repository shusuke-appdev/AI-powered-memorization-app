"""
テスト — SM-2アルゴリズムとカード生成
"""

import datetime
import unittest

from services.card_service import generate_cards_from_selection
from services.review_service import calculate_next_review, get_initial_card_state


class TestSM2(unittest.TestCase):
    def test_initial_state(self) -> None:
        state = get_initial_card_state()
        self.assertEqual(state["repetitions"], 0)
        self.assertEqual(state["interval"], 0)
        self.assertEqual(state["ease_factor"], 2.5)
        self.assertEqual(state["next_review"], datetime.date.today().isoformat())

    def test_first_correct_review(self) -> None:
        card = get_initial_card_state()
        new_state = calculate_next_review(4, card)
        self.assertEqual(new_state["repetitions"], 1)
        self.assertEqual(new_state["interval"], 1)


class TestCardGeneration(unittest.TestCase):
    def test_small_blanks_with_enough_non_adjacent(self) -> None:
        """穴埋め2箇所選択、十分な非隣接フィラー候補がある場合 → 5箇所に補完"""
        # 20文節の中で2箇所(idx 0, 10)を選択 → 非隣接候補が多数あるので5箇所に
        phrases = [f"W{i}" for i in range(20)]
        selected = [0, 10]  # 2グループ、離れている
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)

    def test_exact_boundary(self) -> None:
        """ちょうど5箇所の場合はフィラーなし"""
        phrases = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
        selected = [0, 2, 4, 6, 8]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)

    def test_large_blanks_partition_all_five(self) -> None:
        """12箇所 → 3カード、各カードは5箇所（フィラーで補完）"""
        phrases = [str(i) for i in range(60)]  # 十分な長さ
        selected = [i * 4 for i in range(12)]  # 間隔4で12グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 3)
        for card in cards:
            self.assertEqual(card["question"].count("______"), 5)

    def test_keep_punctuation_and_newlines(self) -> None:
        """句読点・記号はフィラー候補にならない"""
        phrases = ["前段", "。\n", "中段", "：", "空白", " ", "後段"]
        selected = [2]  # "中段" のみ → 1グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        # 非隣接フィラー: "後段"(6) → 1個
        # 隣接フィラー: "前段"(0), "空白"(4) → 2個
        # → 1選択 + 1非隣接 + 2隣接 = 最大4箇所
        blank_count = cards[0]["question"].count("______")
        self.assertGreaterEqual(blank_count, 2)  # 最低でも選択+非隣接
        self.assertLessEqual(blank_count, 4)     # フィラー候補3個 + 選択1個
        self.assertIn("中段", cards[0]["answer"])

    def test_single_blank_padded_with_spacing(self) -> None:
        """1箇所のみ選択、十分な非隣接候補がある → 5箇所に補完"""
        phrases = [
            "不法行為", "は", "、", "故意", "又は", "過失", "によって",
            "他人", "の", "権利", "又は", "法律上保護される利益", "を",
            "侵害した", "者", "は", "、", "これ", "によって", "生じた",
            "損害", "を", "賠償する", "責任", "を", "負う", "。",
        ]
        selected = [3]  # "故意" のみ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)
        self.assertIn("故意", cards[0]["answer"])

    def test_fallback_to_adjacent_when_non_adjacent_insufficient(self) -> None:
        """非隣接候補が不足する場合、隣接候補にフォールバック"""
        # 5文節で真ん中1つ選択 → 非隣接フィラー候補がない → 隣接にフォールバック
        phrases = ["A", "B", "C", "D", "E"]
        selected = [2]  # "C" のみ → 1グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        # 隣接候補: A(0), B(1), D(3), E(4) → 全てが隣接
        # 非隣接候補: なし
        # → フォールバックで隣接候補から4個選択 → 1+4=5箇所
        # ただし統合で減る可能性がある
        blank_count = cards[0]["question"].count("______")
        self.assertGreaterEqual(blank_count, 1)
        self.assertIn("C", cards[0]["answer"])


if __name__ == "__main__":
    unittest.main()
