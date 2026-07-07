"""Toolbar button row, extracted from main_screen.py so replay/timeline/
what-if screens (Phase 4) and the future dashboard shell (Phase 3) can reuse
the exact same button set instead of duplicating it. Behavior is unchanged
from the original inline version in main_screen.py: same labels, same
shortcuts (bound separately in App._bind_shortcuts), same commands."""
import tkinter as tk


def build_toolbar(parent, app, theme) -> tk.Frame:
    """`app` is the App controller; buttons call back into its cross-screen
    actions (dialogs, save/load, undo). Returns an unpacked tk.Frame -- the
    caller decides how to place it (matches the .pack()-after-build
    convention every other cluedo.gui.*.build() function follows)."""
    toolbar = tk.Frame(parent, bg=theme.bg)

    def make_button(text, command):
        tk.Button(toolbar, text=text, command=command, font=theme.body_font(10), padx=8, pady=4).pack(
            side="left", padx=3
        )

    make_button("Log Suggestion (Ctrl+N)", app.open_suggestion_dialog)
    make_button("Undo (Ctrl+Z)", app.undo)
    make_button("Timeline (Ctrl+E)", app.open_timeline)
    make_button("Replay (Ctrl+R)", app.open_replay)
    make_button("What-If", app.open_whatif)
    make_button("Trends", app.open_graphs)
    make_button("Review", app.open_game_review)
    make_button("World Explorer", app.open_world_explorer)
    make_button("Turn Inspector", app.open_turn_inspector)
    make_button("Envelope Explorer", app.open_envelope_explorer)
    make_button("Compare Suggestions", app.open_suggestion_comparison)
    make_button("Simulator", app.open_recommendation_simulator)
    make_button("Movement", app.open_movement_screen)
    make_button("Save (Ctrl+S)", app.save)
    make_button("Load (Ctrl+O)", app.load)
    make_button("Export", app.open_export)
    make_button("Settings", app.open_settings)

    return toolbar
