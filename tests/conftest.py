import pytest

from cluedo.config import load_bundled_edition
from cluedo.models import Player


@pytest.fixture
def cfg():
    return load_bundled_edition("classic_uk")


@pytest.fixture
def cards_by_name(cfg):
    return {c.name: c for c in cfg.all_cards()}


@pytest.fixture
def three_players():
    return [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]
