import tkinter as tk
from tkinter import filedialog, messagebox

from cluedo.game import GameState, SaveFileError, default_autosave_path, load_game, save_game
from cluedo.gui import (
    edition_select_screen,
    explain_dialog,
    export_dialog,
    hand_screen,
    main_screen,
    replay_screen,
    setup_screen,
    suggestion_dialog,
    timeline_screen,
    whatif_screen,
)
from cluedo.gui.theme import LIGHT, ThemeManager


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cluedo Deduction Assistant")
        self.root.geometry("1150x760")
        self.root.minsize(950, 620)

        self.theme_manager = ThemeManager(LIGHT)
        self.theme_manager.subscribe(self._on_theme_changed)
        self.root.configure(bg=self.theme_manager.current.bg)

        self.game_state: GameState | None = None
        self.pending_config = None
        self._current_frame = None
        self._current_screen_show = lambda: None
        self.refresh_main_screen = lambda: None

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

    def _on_edition_selected(self, config):
        self.pending_config = config
        self._current_screen_show = lambda: self._on_edition_selected(config)
        self._swap(setup_screen.build(self.root, self.theme_manager.current, config, self._on_setup_confirmed))

    def _on_setup_confirmed(self, players, user_seat):
        self.game_state = GameState(self.pending_config, players, user_seat)
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

    # -------------------------------------------------------------- actions

    def after_mutation(self):
        self._autosave()
        self.refresh_main_screen()

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

    def open_explain(self, card):
        if self.game_state:
            explain_dialog.open_explain(self, card)

    def open_export(self):
        if self.game_state:
            export_dialog.open_export(self)

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
        self.show_main_screen()
        return True

    # ------------------------------------------------------------ shortcuts

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-z>", lambda e: self.undo())
        self.root.bind_all("<Control-s>", lambda e: self.save())
        self.root.bind_all("<Control-o>", lambda e: self.load())
        self.root.bind_all("<Control-n>", lambda e: self.open_suggestion_dialog())
        self.root.bind_all("<Control-e>", lambda e: self.open_timeline())
        self.root.bind_all("<Control-r>", lambda e: self.open_replay())

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
