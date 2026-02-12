import unittest
from utils import calculate_next_review, get_initial_card_state
import datetime

class TestSM2(unittest.TestCase):
    def test_initial_state(self):
        state = get_initial_card_state()
        self.assertEqual(state['repetitions'], 0)
        self.assertEqual(state['interval'], 0)
        self.assertEqual(state['ease_factor'], 2.5)
        self.assertEqual(state['next_review'], datetime.date.today().isoformat())

    def test_first_correct_review(self):
        card = get_initial_card_state()
        # Quality 4: Good
        new_state = calculate_next_review(4, card)
        
        self.assertEqual(new_state['repetitions'], 1)
        self.assertEqual(new_state['interval'], 1)
        self.assertTrue(new_state['ease_factor'] == 2.5) # EF doesn't change for q=4
        
        expected_next_review = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(new_state['next_review'], expected_next_review)

    def test_second_correct_review(self):
        card = get_initial_card_state()
        card['repetitions'] = 1
        card['interval'] = 1
        
        # Quality 5: Easy
        new_state = calculate_next_review(5, card)
        
        self.assertEqual(new_state['repetitions'], 2)
        self.assertEqual(new_state['interval'], 6)
        self.assertTrue(new_state['ease_factor'] > 2.5) # EF increases for q=5

    def test_incorrect_review(self):
        card = get_initial_card_state()
        card['repetitions'] = 5
        card['interval'] = 10
        
        # Quality 1: Incorrect
        new_state = calculate_next_review(1, card)
        
        self.assertEqual(new_state['repetitions'], 0)
        self.assertEqual(new_state['interval'], 1)
        self.assertTrue(new_state['ease_factor'] < 2.5) # EF decreases

if __name__ == '__main__':
    unittest.main()
