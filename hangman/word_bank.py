from typing import Dict, List
import random

WORD_BANK: Dict[str, List[str]] = {
    "EASY": [
        "DOG",
        "TREE",
        "PYTHON",
        "SUN",
        "HOUSE"
    ],
    "MEDIUM": [
        "SOFTWARE",
        "LAPTOP",
        "COMPUTER",
        "NOTEBOOK",
        "DATABASE"
    ],
    "HARD": [
        "ARTIFICIAL INTELLIGENCE",
        "NEURAL NETWORK",
        "DISTRIBUTED SYSTEMS",
        "OBJECT ORIENTED PROGRAMMING",
        "MICROSERVICES ARCHITECTURE"
    ],
}

def get_random_word(difficulty: str) -> str:
    difficulty = difficulty.strip().upper()
    if difficulty not in WORD_BANK:
        raise ValueError("Invalid difficulty level.")
    return random.choice(WORD_BANK[difficulty])