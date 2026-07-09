import time
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox

from cluedo import __version__
from cluedo.game import GameState, SaveFileError, default_autosave_path, load_game, save_game
from cluedo.gui import (
    deduction_graph_screen,
    edition_select_screen,
    envelope_explorer_screen,
    explain_dialog,
    export_dialog,
    game_review_screen,
    graph_screen,
    hand_screen,
    main_screen,
    movement_screen,
    recommendation_simulator_screen,
    replay_screen,
    settings_screen,
    setup_screen,
    suggestion_comparison_screen,
    suggestion_dialog,
    timeline_screen,
    turn_inspector_screen,
    whatif_screen,
    world_explorer_screen,
)
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.gui.window_geometry import fit_geometry
from cluedo.persistence.player_store import PlayerStore


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"Cluedo Deduction Assistant v{__version__}")
        fit_geometry(self.root, 1150, 760, min_width=950, min_height=620)

        self.theme_manager = ThemeManager(LIGHT)
        self.theme_manager.subscribe(self._on_theme_changed)
        self.root.configure(bg=self.theme_manager.current.bg)

        self.game_state: GameState | None = None
        self.pending_config = None
        self._edition_key: str | None = None
        self._movement_graph_cache = None
        self._movement_graph_cache_key: str | None = None
        self._current_frame = None
        self._current_screen_show = lambda: None
        self.refresh_main_screen = lambda: None
        # Non-modal auxiliary windows (e.g. Timeline) that must stay in sync
        # with the live GameState while open register here instead of
        # relying on refresh_main_screen, which only ever points at whatever
        # single screen is current.
        self._mutation_listeners = []

        self.player_store = PlayerStore()
        self._game_id: str | None = None
        self._game_end_recorded = False
        self._game_start_wall_clock: float | None = None
        self._game_review_shown = False
        self._game_review_cache = None

        self._bind_shortcuts()
        if not self._maybe_offer_recovery():
            self.show_edition_select()

    # ---------------------------------------------------------------- screens

    def _swap(self, frame):
        if self._current_frame is not None:
            self._current_frame.destroy()
        self._current_frame = frame
        frame.pack(fill="both", expand=True)

    def _on_theme_changed(self, theme):
        self.root.configure(bg=theme.bg)
        self._current_screen_show()

    def show_edition_select(self):
        self._current_screen_show = self.show_edition_select
        self._swap(edition_select_screen.build(self.root, self.theme_manager.current, self._on_edition_selected))

    def _on_edition_selected(self, config, edition_key=None):
        self.pending_config = config
        self._edition_key = edition_key
        self._current_screen_show = lambda: self._on_edition_selected(config, edition_key)
        self._swap(setup_screen.build(self.root, self.theme_manager.current, config, self._on_setup_confirmed))

    def _on_setup_confirmed(self, players, user_seat):
        self.game_state = GameState(self.pending_config, players, user_seat)
        self._start_tracking_game()
        expected = players[user_seat].hand_size
        self._current_screen_show = lambda: self._on_setup_confirmed(players, user_seat)
        self._swap(
            hand_screen.build(
                self.root, self.theme_manager.current, self.pending_config, expected, self._on_hand_confirmed
            )
        )

    def _on_hand_confirmed(self, cards):
        self.game_state.set_user_hand(cards)
        self.show_main_screen()

    def show_main_screen(self):
        self._current_screen_show = self.show_main_screen
        self._swap(main_screen.build(self.root, self))

    # ---------------------------------------------------- player_store sync

    def _start_tracking_game(self):
        """Called once per game (new setup, load, or crash recovery) to begin
        mirroring it into `self.player_store`. Safe to call repeatedly for the
        same GameState -- record_game_start upserts by game_id."""
        if self.game_state is None:
            return
        self._game_id = uuid.uuid4().hex
        self._game_end_recorded = False
        self._game_start_wall_clock = time.monotonic()
        self._game_review_shown = False
        self._game_review_cache = None
        self.player_store.record_game_start(
            self._game_id, self.game_state.config.edition, self.game_state.players
        )
        self._sync_player_store()

    def _game_review_time_played_seconds(self) -> "float | None":
        """Elapsed wall-clock time since `_start_tracking_game()` began
        tracking the current game, THIS session -- not a cumulative total
        across save/load boundaries (the JSON save format carries no
        timestamps, and adding them would be a save-format change; this is
        an honest "how long have you been playing since you (re)opened this
        game" figure instead, clearly labeled as such wherever it's shown)."""
        if self._game_start_wall_clock is None:
            return None
        return time.monotonic() - self._game_start_wall_clock

    def _sync_player_store(self):
        """Mirrors the live GameState into `self.player_store`: every current
        suggestion (upserted by index, so edits overwrite cleanly) plus a
        one-shot game-end record once solved. Called after every mutation,
        matching this store's own "treat it like autosave" design.

        Known limitation: undo/delete shrinking history doesn't retract the
        now-stale trailing rows from a previous longer history -- an
        acceptable gap for this analytics-only mirror (it never feeds back
        into the solver), not worth a new PlayerStore deletion API for.
        """
        if self.game_state is None or self._game_id is None:
            return
        for index, suggestion in enumerate(self.game_state.history):
            self.player_store.record_suggestion(self._game_id, index, suggestion)

        if self.game_state.is_solved() and not self._game_end_recorded:
            self._game_end_recorded = True
            self.player_store.record_game_end(
                self._game_id, True, len(self.game_state.history), self.game_state.solution()
            )

    # -------------------------------------------------------------- actions

    def after_mutation(self):
        self._autosave()
        self._sync_player_store()
        # A game can go from solved back to unsolved (undo, or deleting/
        # editing the solving suggestion via Timeline) -- rearm the
        # once-per-game Game Review guard so a later, different solve
        # recomputes its own review instead of _maybe_auto_open_review
        # silently no-oping and leaving the sidebar card showing the
        # *first* solve's stale grade/efficiency/turning-point data.
        if self._game_review_shown and self.game_state is not None and not self.game_state.is_solved():
            self._game_review_shown = False
            self._game_review_cache = None
        # Compute/cache the Game Review (and auto-open its popup) *before*
        # refreshing the sidebar, so the Game Review card can show the
        # summary on the very turn that solves the game instead of lagging
        # one refresh behind.
        self._maybe_auto_open_review()
        self.refresh_main_screen()
        for listener in list(self._mutation_listeners):
            listener()

    def add_mutation_listener(self, callback):
        """Registers `callback` to run after every mutation (new suggestion,
        undo, edit, delete). Caller is responsible for calling
        remove_mutation_listener once its window closes."""
        self._mutation_listeners.append(callback)

    def remove_mutation_listener(self, callback):
        if callback in self._mutation_listeners:
            self._mutation_listeners.remove(callback)

    def open_suggestion_dialog(self):
        if self.game_state:
            suggestion_dialog.open_dialog(self)

    def open_timeline(self):
        if self.game_state:
            timeline_screen.open_timeline(self)

    def open_replay(self):
        if self.game_state:
            replay_screen.open_replay(self)

    def open_whatif(self):
        if self.game_state:
            whatif_screen.open_whatif(self)

    def open_graphs(self):
        if self.game_state:
            graph_screen.open_graphs(self)

    def open_settings(self):
        settings_screen.open_settings(self)

    def open_game_review(self):
        if self.game_state:
            game_review_screen.open_game_review(self)

    def _maybe_auto_open_review(self):
        """After every completed game, automatically show the Game Review --
        once per game (guarded the same way _game_end_recorded guards the
        player_store write), not on every subsequent refresh. Caches the
        computed GameReview on `self._game_review_cache` so the sidebar's
        Game Review card can display a summary without recomputing this
        expensive, solver-derived report a second time."""
        if self.game_state is None or self._game_review_shown or not self.game_state.is_solved():
            return
        self._game_review_shown = True
        from cluedo.analysis.game_review import compute_game_review

        review = compute_game_review(self.game_state, time_played_seconds=self._game_review_time_played_seconds())
        self._game_review_cache = review
        game_review_screen.open_game_review(self, review=review)

    def open_explain(self, card):
        if self.game_state:
            explain_dialog.open_explain(self, card)

    def open_export(self):
        if self.game_state:
            export_dialog.open_export(self)

    def open_world_explorer(self):
        if self.game_state:
            world_explorer_screen.open_world_explorer(self)

    def open_turn_inspector(self, turn_index=None):
        if self.game_state:
            turn_inspector_screen.open_turn_inspector(self, turn_index)

    def open_deduction_graph(self, card):
        if self.game_state:
            deduction_graph_screen.open_deduction_graph(self, card)

    def open_envelope_explorer(self):
        if self.game_state:
            envelope_explorer_screen.open_envelope_explorer(self)

    def open_suggestion_comparison(self):
        if self.game_state:
            suggestion_comparison_screen.open_suggestion_comparison(self)

    def open_recommendation_simulator(self, detailed_candidate=None):
        if self.game_state:
            recommendation_simulator_screen.open_recommendation_simulator(self, detailed_candidate)

    def open_movement_screen(self):
        if self.game_state:
            movement_screen.open_movement_screen(self)

    def current_movement_graph(self):
        """The MovementGraph for the live game's edition, or None if no
        movement data is bundled for it (e.g. classic_uk/classic_us, a
        custom-loaded edition, or a loaded save file -- the edition key
        isn't part of the save format, so reloaded games fall back to this
        same graceful "unsupported" state). Cached per edition key so the
        graph (and its all-pairs shortest-path precompute) is never rebuilt
        unnecessarily."""
        if self.game_state is None or self._edition_key is None:
            return None
        if self._movement_graph_cache is None or self._movement_graph_cache_key != self._edition_key:
            from cluedo.movement.graph import MovementGraph

            self._movement_graph_cache = MovementGraph.from_edition(self._edition_key, self.game_state.config.rooms)
            self._movement_graph_cache_key = self._edition_key
        return self._movement_graph_cache

    def invalidate_movement_graph(self):
        """Forces the next current_movement_graph() call to rebuild from
        disk -- called after the Edit Board Data dialog saves or resets a
        user override, so corrected distances/passages take effect
        immediately instead of waiting for a fresh edition switch."""
        self._movement_graph_cache = None
        self._movement_graph_cache_key = None

    def undo(self):
        if self.game_state and self.game_state.history:
            self.game_state.undo_last_suggestion()
            self.after_mutation()

    def save(self):
        if not self.game_state:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Cluedo save", "*.json")])
        if not path:
            return
        save_game(self.game_state, path)
        messagebox.showinfo("Saved", f"Game saved to {path}")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("Cluedo save", "*.json")])
        if not path:
            return
        try:
            self.game_state = load_game(path)
        except SaveFileError as exc:
            messagebox.showerror("Couldn't load file", str(exc))
            return
        # Loaded saves don't carry a bundled edition key (not part of the
        # save format), so movement data gracefully reports "unsupported"
        # for reloaded games rather than guessing at a key.
        self._edition_key = None
        self._start_tracking_game()
        self.show_main_screen()

    def _autosave(self):
        if not self.game_state:
            return
        try:
            save_game(self.game_state, default_autosave_path())
        except OSError:
            pass  # autosave is best-effort; never interrupt play over it

    def _maybe_offer_recovery(self) -> bool:
        path = default_autosave_path()
        if not path.exists():
            return False
        if not messagebox.askyesno("Recover previous session?", "An autosaved game was found. Recover it?"):
            return False
        try:
            self.game_state = load_game(path)
        except SaveFileError as exc:
            messagebox.showerror("Couldn't recover", str(exc))
            return False
        self._start_tracking_game()
        self.show_main_screen()
        return True

    # ------------------------------------------------------------ shortcuts

    def _guarded(self, action):
        """Wraps a global shortcut so it's a no-op while a text-entry-like
        widget has focus. `bind_all` fires regardless of focus, and Tk's
        built-in Entry/Spinbox bindings only claim Ctrl-A/B/D/E/F/H/K/T/W --
        not Z/S/O/N/E/R -- so without this guard, e.g. typing Ctrl-Z while
        correcting a value in "Edit Board Data" silently calls self.undo()
        (deleting the player's last logged suggestion) instead of editing
        text, and Ctrl-O pops the load-file dialog mid-keystroke."""

        def _handler(event):
            focused = self.root.focus_get()
            if isinstance(focused, (tk.Entry, tk.Spinbox, tk.Text)):
                return
            action()

        return _handler

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-z>", self._guarded(self.undo))
        self.root.bind_all("<Control-s>", self._guarded(self.save))
        self.root.bind_all("<Control-o>", self._guarded(self.load))
        self.root.bind_all("<Control-n>", self._guarded(self.open_suggestion_dialog))
        self.root.bind_all("<Control-e>", self._guarded(self.open_timeline))
        self.root.bind_all("<Control-r>", self._guarded(self.open_replay))

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
