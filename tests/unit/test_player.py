import pytest
from hangman.model.player import Player


# ======================================================
# Core Factory Fixture
# ======================================================

@pytest.fixture
def make_player():
    def _make_player(
        name="Alice",
        max_health=5,
        hangman_states=None
    ):
        if hangman_states is None:
            hangman_states = ["state1", "state2", "state3"]

        return Player(
            name=name,
            max_health=max_health,
            hangman_states=hangman_states
        )

    return _make_player


# ======================================================
# Semantic Fixtures (State-Oriented)
# ======================================================

@pytest.fixture
def player(make_player):
    return make_player()


@pytest.fixture
def low_health_player(make_player):
    return make_player(max_health=1)


@pytest.fixture
def dead_player(make_player):
    player = make_player(max_health=1)
    player.lose_health()
    return player


# ======================================================
# Constructor Behavior
# ======================================================

@pytest.mark.parametrize(
    "name, max_health, states",
    [
        ("Alice", 5, ["s1", "s2"]),
        ("Player_123", 4, ["a", "b", "c"]),
        ("Bob", 1, []),
    ]
)
def test_constructor_initializes_attributes(make_player, name, max_health, states):
    player = make_player(name=name, max_health=max_health, hangman_states=states)

    assert player.name == name
    assert player.max_health == max_health
    assert player.health == max_health
    assert player.hangman_states == states


def test_health_starts_equal_to_max_health(player):
    assert player.health == player.max_health


# ======================================================
# Health Decrement Logic (lose_health)
# ======================================================


def test_lose_health_decrements_by_one(player):
    initial = player.health

    player.lose_health()

    assert player.health == initial - 1


@pytest.mark.parametrize(
    "initial_health, expected_health, expected_return",
    [
        (5, 4, False),
        (2, 1, False),
        (1, 0, True),
        (0, 0, False),
    ]
)
def test_lose_health_behavior(make_player, initial_health, expected_health, expected_return):
    player = make_player(max_health=initial_health)

    player.health = initial_health

    result = player.lose_health()

    assert player.health == expected_health
    assert result is expected_return


def test_lose_health_is_idempotent_at_zero(make_player):
    player = make_player(max_health=1)

    player.lose_health() 
    player.lose_health()
    player.lose_health()

    assert player.health == 0


# ======================================================
# Life State Logic (is_alive)
# ======================================================

@pytest.mark.parametrize(
    "health, expected",
    [
        (5, True),
        (1, True),
        (0, False),
    ]
)
def test_is_alive(make_player, health, expected):
    player = make_player(max_health=max(health, 1))
    player.health = health

    assert player.is_alive() is expected


def test_is_alive_after_transition(low_health_player):
    low_health_player.lose_health()

    assert low_health_player.is_alive() is False