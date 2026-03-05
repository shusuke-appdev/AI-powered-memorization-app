import datetime
import unittest

from gemini_client import generate_cards_from_selection
from utils import calculate_next_review, get_initial_card_state


class TestSM2(unittest.TestCase):
    # SM2 tests omitted for brevity (same as before)
    def test_initial_state(self):
        state = get_initial_card_state()
        self.assertEqual(state["repetitions"], 0)
        self.assertEqual(state["interval"], 0)
        self.assertEqual(state["ease_factor"], 2.5)
        self.assertEqual(state["next_review"], datetime.date.today().isoformat())

    def test_first_correct_review(self):
        card = get_initial_card_state()
        new_state = calculate_next_review(4, card)
        self.assertEqual(new_state["repetitions"], 1)
        self.assertEqual(new_state["interval"], 1)


class TestCardGeneration(unittest.TestCase):
    def test_small_blanks(self):
        # 3 separated blanks -> 1 card
        phrases = ["A", "B", "C", "D", "E"]
        selected = [0, 2, 4]  # Indices 0, 2, 4 are separated by 1, 3
        # merge_adjacent_selections sees: [0], [2], [4] -> 3 groups
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 3)

    def test_exact_boundary(self):
        # 5 separated blanks -> 1 card
        phrases = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
        selected = [0, 2, 4, 6, 8]  # 5 groups
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)

    def test_large_blanks_partition(self):
        # 12 separated blanks -> ceil(12/5) = 3 cards
        # Indices: 0, 2, 4, ..., 22
        phrases = [str(i) for i in range(30)]
        selected = [i * 2 for i in range(12)]  # 0, 2, 4, ..., 22
        # This creates 12 separate groups

        cards = generate_cards_from_selection(phrases, selected)

        self.assertEqual(len(cards), 3)

        total_blanks = sum(c["question"].count("______") for c in cards)
        self.assertEqual(total_blanks, 12)

        # Check max blanks per card is 5
        for card in cards:
            self.assertLessEqual(card["question"].count("______"), 5)
            # Ensure at least 1 blank
            self.assertGreater(card["question"].count("______"), 0)

    def test_keep_punctuation_and_newlines(self):
        # 記号や改行、スペースを含むテキストの分割とカード生成テスト
        phrases = ["前段", "。\n", "中段", "：", "空白", " ", "後段"]
        selected = [2]  # "中段" を穴埋めとする
        cards = generate_cards_from_selection(phrases, selected)

        self.assertEqual(len(cards), 1)
        # 穴埋め箇所が正しく置換され、かつ他の文字（改行や記号、スペース）が失われていないか確認
        self.assertEqual(cards[0]["question"], "前段。\n______：空白 後段")
        self.assertEqual(cards[0]["answer"], "中段")


if __name__ == "__main__":
    unittest.main()
