"""
テスト — SM-2アルゴリズムとカード生成
"""

import datetime
import unittest

from services.card_service import apply_highlight, generate_cards_from_selection
from services.review_service import (
    calculate_next_review,
    get_initial_card_state,
    reconcile_daily_quota,
    select_hybrid_quota,
)


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


class TestDailyQuotaSelection(unittest.TestCase):
    def test_duplicate_quota_ids_are_repaired_and_topped_up(self) -> None:
        cards = [_make_review_card(str(i)) for i in range(20)]

        quota_ids = reconcile_daily_quota(
            ["0"] * 20,
            [],
            cards,
            daily_limit=20,
            all_cards=cards,
        )

        self.assertEqual(len(quota_ids), 20)
        self.assertEqual(len(set(quota_ids)), 20)
        self.assertEqual(quota_ids[0], "0")

    def test_reviewed_cards_survive_quota_session_reset(self) -> None:
        cards = [_make_review_card(str(i)) for i in range(25)]

        quota_ids = reconcile_daily_quota(
            None,
            ["0", "1", "2"],
            cards[3:],
            daily_limit=20,
            all_cards=cards,
        )

        self.assertEqual(len(quota_ids), 20)
        self.assertEqual(quota_ids[:3], ["0", "1", "2"])
        self.assertEqual(len(set(quota_ids)), 20)

    def test_quota_shrink_keeps_already_reviewed_cards(self) -> None:
        cards = [_make_review_card(str(i)) for i in range(25)]

        quota_ids = reconcile_daily_quota(
            [str(i) for i in range(20)],
            [str(i) for i in range(15)],
            cards[15:],
            daily_limit=10,
            all_cards=cards,
        )

        self.assertEqual(quota_ids, [str(i) for i in range(15)])

    def test_select_hybrid_quota_deduplicates_candidate_card_ids(self) -> None:
        cards = [_make_review_card("0"), _make_review_card("0"), _make_review_card("1")]

        selected = select_hybrid_quota(cards, 3, cards)

        self.assertEqual([card["id"] for card in selected], ["0", "1"])

    def test_select_hybrid_quota_keeps_unique_ids_after_blank_adjustment(self) -> None:
        due_cards = [
            _make_review_card(str(i), blank_count=1, rank="A+") for i in range(20)
        ]
        due_cards.extend(
            _make_review_card(str(i), blank_count=5, rank="C") for i in range(20, 30)
        )

        selected = select_hybrid_quota(due_cards, 20, due_cards)
        selected_ids = [card["id"] for card in selected]

        self.assertEqual(len(selected), 20)
        self.assertEqual(len(set(selected_ids)), 20)

    def test_initial_quota_reconciliation_returns_daily_limit_unique_ids(self) -> None:
        due_cards = [
            _make_review_card(str(i), blank_count=1, rank="A+") for i in range(20)
        ]
        due_cards.extend(
            _make_review_card(str(i), blank_count=5, rank="C") for i in range(20, 30)
        )

        quota_ids = reconcile_daily_quota(
            None,
            [],
            due_cards,
            daily_limit=20,
            all_cards=due_cards,
        )

        self.assertEqual(len(quota_ids), 20)
        self.assertEqual(len(set(quota_ids)), 20)


class TestCardGeneration(unittest.TestCase):
    def test_single_blank_no_filler(self) -> None:
        """1箇所のみ選択 → フィラーなし、穴埋め1箇所のカード1枚"""
        phrases = [
            "不法行為",
            "は",
            "、",
            "故意",
            "又は",
            "過失",
            "によって",
            "他人",
            "の",
            "権利",
            "又は",
            "法律上保護される利益",
            "を",
            "侵害した",
            "者",
            "は",
            "、",
            "これ",
            "によって",
            "生じた",
            "損害",
            "を",
            "賠償する",
            "責任",
            "を",
            "負う",
            "。",
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


class TestHtmlSafety(unittest.TestCase):
    def test_apply_highlight_escapes_html_without_keywords(self) -> None:
        text = '<script>alert("x")</script>'
        self.assertEqual(
            apply_highlight(text, ""),
            "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;",
        )

    def test_apply_highlight_escapes_html_with_keywords(self) -> None:
        result = apply_highlight("<b>民法</b>", "民法")
        self.assertIn("&lt;b&gt;", result)
        self.assertIn("&lt;/b&gt;", result)
        self.assertIn(">民法</span>", result)
        self.assertNotIn("<b>", result)


def _make_review_card(
    card_id: str,
    *,
    blank_count: int = 1,
    rank: str = "B",
    category: str = "民法",
) -> dict[str, object]:
    return {
        "id": card_id,
        "question": f"question {card_id}",
        "answer": f"answer {card_id}",
        "category": category,
        "ease_factor": 2.5,
        "next_review": datetime.date.today().isoformat(),
        "blank_count": blank_count,
        "rank": rank,
    }


if __name__ == "__main__":
    unittest.main()
