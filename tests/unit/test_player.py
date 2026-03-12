import pytest
from player import Player


# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def hangman_states():
    return ["state1", "state2", "state3"]


@pytest.fixture
def player(hangman_states):
    return Player(
        name="Alice",
        max_health=5,
        hangman_states=hangman_states
    )


# -----------------------------
# Initialization Tests
# -----------------------------

def test_player_initializes_attributes_correctly(player, hangman_states):
    assert player.name == "Alice"
    assert player.max_health == 5
    assert player.health == 5
    assert player.hangman_states == hangman_states


def test_health_starts_equal_to_max_health(player):
    assert player.health == player.max_health


def test_initialization_with_empty_hangman_states():
    player = Player("Alice", 3, [])
    assert player.hangman_states == []


def test_initialization_with_health_one(hangman_states):
    player = Player("Alice", 1, hangman_states)

    assert player.max_health == 1
    assert player.health == 1


def test_initialization_preserves_player_name(hangman_states):
    player = Player("Player_123", 4, hangman_states)

    assert player.name == "Player_123"