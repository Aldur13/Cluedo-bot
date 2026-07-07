import tkinter as tk

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


@pytest.fixture(scope="session")
def root():
    """Single Tk root shared across every GUI test file in the whole session.
    Creating/tearing down many independent `tk.Tk()` interpreters -- even
    sequentially across different test modules, not just rapidly within one
    -- was observed to intermittently raise `_tkinter.TclError: Can't find a
    usable tk.tcl` on this machine once enough GUI test files existed in one
    run. A single session-scoped root, with each test building/destroying its
    own child Frame/Toplevel, eliminates it."""
    r = tk.Tk()
    yield r
    r.destroy()
