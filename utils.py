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
