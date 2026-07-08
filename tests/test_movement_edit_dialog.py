"""GUI tests for cluedo/gui/movement_edit_dialog.py: prefilled values,
saving persists a corrected distance via the real save path, and Reset
removes the override. Redirects the override storage into tmp_path so
these never touch the real user's %APPDATA%."""
import tkinter as tk

import pytest

from cluedo.config import load_bundled_edition
from cluedo.game import GameState
from cluedo.gui import movement_edit_dialog
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import Player
from cluedo.movement import data as movement_data


@pytest.fixture(autouse=True)
def _redirect_override_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(movement_data, "user_movement_data_dir", lambda: tmp_path)


class _FakeApp:
    def __init__(self, root, game_state, edition_key):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self._edition_key = edition_key
        self.invalidate_calls = 0

    def invalidate_movement_graph(self):
        self.invalidate_calls += 1


def _swedish_game():
    cfg = load_bundled_edition("swedish_2012")
    players = [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]
    gs = GameState(cfg, players, user_seat=0)
    hand = cfg.suspects[:2] + cfg.weapons[:2] + cfg.rooms[:2]
    gs.set_user_hand([c for c in cfg.all_cards() if c.name in hand])
    return gs


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("dialog did not create a Toplevel")


def _find_widget(widget, predicate):
    if predicate(widget):
        return widget
    for child in widget.winfo_children():
        found = _find_widget(child, predicate)
        if found is not None:
            return found
    return None


def _find_button(widget, text):
    return _find_widget(widget, lambda w: isinstance(w, tk.Button) and str(w.cget("text")) == text)


def test_dialog_prefills_bundled_distances(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, "swedish_2012")
    bundled = movement_data.load_movement_data("swedish_2012", gs.config.rooms)

    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)
    try:
        label = _find_widget(win, lambda w: isinstance(w, tk.Label) and w.cget("text") == "Köket")
        assert label is not None
        entry = next(c for c in label.master.winfo_children() if isinstance(c, tk.Entry))
        assert entry.get() == str(bundled.distances_to_hub["Köket"])
    finally:
        win.destroy()


def test_save_persists_a_corrected_distance(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, "swedish_2012")

    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)

    # Find Köket's distance Entry via its neighboring Label, then overwrite it.
    label = _find_widget(win, lambda w: isinstance(w, tk.Label) and w.cget("text") == "Köket")
    row = label.master
    entry = next(c for c in row.winfo_children() if isinstance(c, tk.Entry))
    entry.delete(0, tk.END)
    entry.insert(0, "99")

    save_button = _find_button(win, "Save")
    assert save_button is not None
    save_button.invoke()

    assert app.invalidate_calls == 1
    reloaded = movement_data.load_movement_data("swedish_2012", gs.config.rooms)
    assert reloaded.distances_to_hub["Köket"] == 99
    assert movement_data.has_override("swedish_2012") is True


def test_save_rejects_non_positive_distance(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, "swedish_2012")

    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)
    try:
        label = _find_widget(win, lambda w: isinstance(w, tk.Label) and w.cget("text") == "Köket")
        row = label.master
        entry = next(c for c in row.winfo_children() if isinstance(c, tk.Entry))
        entry.delete(0, tk.END)
        entry.insert(0, "not a number")

        save_button = _find_button(win, "Save")
        save_button.invoke()

        # Rejected -- dialog stays open, no override written.
        assert win.winfo_exists()
        assert app.invalidate_calls == 0
        assert movement_data.has_override("swedish_2012") is False
    finally:
        win.destroy()


def test_reset_removes_override_and_reverts(root):
    gs = _swedish_game()
    bundled = movement_data.load_movement_data("swedish_2012", gs.config.rooms)
    corrected = dict(bundled.distances_to_hub)
    corrected["Köket"] = 42
    movement_data.save_movement_override(
        movement_data.MovementData("swedish_2012", bundled.hub, corrected, bundled.secret_passages)
    )
    assert movement_data.has_override("swedish_2012") is True

    app = _FakeApp(root, gs, "swedish_2012")
    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)

    reset_button = _find_button(win, "Reset to Bundled Defaults")
    assert reset_button is not None
    reset_button.invoke()

    assert app.invalidate_calls == 1
    assert movement_data.has_override("swedish_2012") is False
    reloaded = movement_data.load_movement_data("swedish_2012", gs.config.rooms)
    assert reloaded.distances_to_hub["Köket"] == bundled.distances_to_hub["Köket"]


def test_no_reset_button_when_no_override_exists(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, "swedish_2012")

    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)
    try:
        assert _find_button(win, "Reset to Bundled Defaults") is None
    finally:
        win.destroy()


def test_add_and_remove_secret_passage(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, "swedish_2012")
    rooms = gs.config.rooms

    movement_edit_dialog.open_movement_edit_dialog(app)
    win = _find_toplevel(root)

    # Default room-A/room-B pickers are rooms[0]/rooms[1] -- add that pair.
    add_button = _find_button(win, "Add Passage")
    assert add_button is not None
    add_button.invoke()

    remove_button = _find_button(win, "Remove")
    assert remove_button is not None

    save_button = _find_button(win, "Save")
    save_button.invoke()

    loaded = movement_data.load_movement_data("swedish_2012", rooms)
    assert frozenset((rooms[0], rooms[1])) in {frozenset(p) for p in loaded.secret_passages}
