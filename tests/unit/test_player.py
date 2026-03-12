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

@pytest.fixture
def low_health_player(hangman_states):
    return Player(
        name="Alice",
        max_health=1,
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


# -----------------------------
# lose_health Tests
# -----------------------------

def test_lose_health_reduces_health_by_one(player):
    previous_health = player.health

    player.lose_health()

    assert player.health == previous_health - 1

def test_lose_health_returns_false_when_player_survives(player):
    result = player.lose_health()

    assert result is False
    assert player.health == 4

def test_lose_health_returns_true_when_player_dies(low_health_player):
    result = low_health_player.lose_health()

    assert low_health_player.health == 0
    assert result is True

def test_lose_health_does_not_go_below_zero(low_health_player):
    low_health_player.lose_health()
    low_health_player.lose_health()
    low_health_player.lose_health()

    assert low_health_player.health == 0

def test_lose_health_when_player_already_dead(low_health_player):
    low_health_player.lose_health()

    result = low_health_player.lose_health()

    assert low_health_player.health == 0
    assert result is False

