import json
import os
from utils import get_initial_card_state
import uuid

DATA_FILE = "flashcards.json"

def load_cards():
    """Loads flashcards from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_cards(cards):
    """Saves the list of flashcards to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=4, ensure_ascii=False)

def add_card(question, answer, title="", category="その他"):
    """Adds a new card to the storage."""
    cards = load_cards()
    new_card = {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer": answer,
        "title": title,
        "category": category,
        **get_initial_card_state()
    }
    cards.append(new_card)
    save_cards(cards)
    return new_card

def update_card_progress(card_id, new_state):
    """Updates the progress state of a specific card."""
    cards = load_cards()
    for card in cards:
        if card["id"] == card_id:
            card.update(new_state)
            break
    save_cards(cards)

def delete_card(card_id):
    """Deletes a card with the given ID."""
    cards = load_cards()
    cards = [c for c in cards if c["id"] != card_id]
    save_cards(cards)

def update_card_content(card_id, question, answer, title="", category="その他"):
    """Updates the question, answer, title, and category of a specific card."""
    cards = load_cards()
    for card in cards:
        if card["id"] == card_id:
            card["question"] = question
            card["answer"] = answer
            card["title"] = title
            card["category"] = category
            break
    save_cards(cards)
