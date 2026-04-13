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
    def test_small_blanks(self) -> None:
        phrases = ["A", "B", "C", "D", "E"]
        selected = [0, 2, 4]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 3)

    def test_exact_boundary(self) -> None:
        phrases = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
        selected = [0, 2, 4, 6, 8]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"].count("______"), 5)

    def test_large_blanks_partition(self) -> None:
        phrases = [str(i) for i in range(30)]
        selected = [i * 2 for i in range(12)]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 3)
        total_blanks = sum(c["question"].count("______") for c in cards)
        self.assertEqual(total_blanks, 12)
        for card in cards:
            self.assertLessEqual(card["question"].count("______"), 5)
            self.assertGreater(card["question"].count("______"), 0)

    def test_keep_punctuation_and_newlines(self) -> None:
        phrases = ["前段", "。\n", "中段", "：", "空白", " ", "後段"]
        selected = [2]
        cards = generate_cards_from_selection(phrases, selected)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["question"], "前段。\n______：空白 後段")
        self.assertEqual(cards[0]["answer"], "中段")


if __name__ == "__main__":
    unittest.main()
