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
    def test_single_blank_no_filler(self) -> None:
        """1箇所のみ選択 → フィラーなし、穴埋め1箇所のカード1枚"""
        phrases = [
            "不法行為", "は", "、", "故意", "又は", "過失", "によって",
            "他人", "の", "権利", "又は", "法律上保護される利益", "を",
            "侵害した", "者", "は", "、", "これ", "によって", "生じた",
            "損害", "を", "賠償する", "責任", "を", "負う", "。",
        ]
        selected = [3]  # "故意" のみ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 1)
        self.assertIn("故意", cards[0]["answer"])

    def test_three_blanks_no_filler(self) -> None:
        """3箇所選択 → フィラーなし、穴埋め3箇所のカード1枚"""
        phrases = ["A", "B", "C", "D", "E", "F", "G"]
        selected = [0, 2, 6]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 3)

    def test_exact_five_blanks(self) -> None:
        """ちょうど5箇所 → カード1枚、穴埋め5箇所"""
        phrases = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
        selected = [0, 2, 4, 6, 8]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)

    def test_six_blanks_two_cards(self) -> None:
        """6箇所 → 2カード、各5箇所（重複あり）"""
        phrases = [str(i) for i in range(20)]
        selected = [0, 3, 6, 9, 12, 15]  # 6グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 2)
        # 1枚目は5箇所
        self.assertEqual(cards[0]["question"].count("______"), 5)
        # 2枚目も5箇所（残り1箇所＋他から4箇所補充で計5箇所）
        self.assertEqual(cards[1]["question"].count("______"), 5)

    def test_twelve_blanks_three_cards(self) -> None:
        """12箇所 → 3カード、各5箇所（最後のカードは重複補充）"""
        phrases = [str(i) for i in range(60)]
        selected = [i * 4 for i in range(12)]  # 間隔4で12グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 3)
        for card in cards:
            self.assertEqual(card["question"].count("______"), 5)

    def test_all_blanks_covered(self) -> None:
        """全ての穴埋め箇所が少なくとも1枚のカードに含まれる"""
        phrases = [str(i) for i in range(30)]
        selected = [1, 5, 9, 13, 17, 21, 25]  # 7グループ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 2)
        # 全ての選択された文節がいずれかのカードのanswerに含まれる
        all_answers = " ".join(c["answer"] for c in cards)
        for idx in selected:
            self.assertIn(str(idx), all_answers)

    def test_keep_punctuation_not_selected(self) -> None:
        """句読点は穴埋め対象にならず、ユーザー選択のみ穴埋め"""
        phrases = ["前段", "。\n", "中段", "：", "空白", " ", "後段"]
        selected = [2]  # "中段" のみ
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 1)
        self.assertIn("中段", cards[0]["answer"])

    def test_empty_selection(self) -> None:
        """空の選択 → カードなし"""
        phrases = ["A", "B", "C"]
        selected: list[int] = []
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 0)


if __name__ == "__main__":
    unittest.main()
