"""Toolbar button row, extracted from main_screen.py so replay/timeline/
what-if screens (Phase 4) and the future dashboard shell (Phase 3) can reuse
the exact same button set instead of duplicating it. Behavior is unchanged
from the original inline version in main_screen.py: same labels, same
shortcuts (bound separately in App._bind_shortcuts), same commands.

Wrapped across two rows (added in v4.6, once the button count grew past
what fits on one row at typical window widths -- Movement was the button
that first ran off-screen with no way to reach it). The public contract is
unchanged: build_toolbar still returns one `tk.Frame` the caller packs
exactly as before; only the internal structure gained a row of nesting."""
import tkinter as tk


def build_toolbar(parent, app, theme) -> tk.Frame:
    """`app` is the App controller; buttons call back into its cross-screen
    actions (dialogs, save/load, undo). Returns an unpacked tk.Frame -- the
    caller decides how to place it (matches the .pack()-after-build
    convention every other cluedo.gui.*.build() function follows)."""
    toolbar = tk.Frame(parent, bg=theme.bg)
    row1 = tk.Frame(toolbar, bg=theme.bg)
    row2 = tk.Frame(toolbar, bg=theme.bg)
    row1.pack(side="top", fill="x")
    row2.pack(side="top", fill="x", pady=(4, 0))

    def make_button(row, text, command):
        tk.Button(row, text=text, command=command, font=theme.body_font(10), padx=8, pady=4).pack(
            side="left", padx=3
        )

    # Row 1: core gameplay actions (logging, reviewing, and navigating the
    # game as it's played).
    make_button(row1, "Log Suggestion (Ctrl+N)", app.open_suggestion_dialog)
    make_button(row1, "Undo (Ctrl+Z)", app.undo)
    make_button(row1, "Timeline (Ctrl+E)", app.open_timeline)
    make_button(row1, "Replay (Ctrl+R)", app.open_replay)
    make_button(row1, "What-If", app.open_whatif)
    make_button(row1, "Trends", app.open_graphs)
    make_button(row1, "Review", app.open_game_review)
    make_button(row1, "Save (Ctrl+S)", app.save)
    make_button(row1, "Load (Ctrl+O)", app.load)

    # Row 2: deeper analysis tools plus file/settings actions.
    make_button(row2, "World Explorer", app.open_world_explorer)
    make_button(row2, "Turn Inspector", app.open_turn_inspector)
    make_button(row2, "Envelope Explorer", app.open_envelope_explorer)
    make_button(row2, "Compare Suggestions", app.open_suggestion_comparison)
    make_button(row2, "Simulator", app.open_recommendation_simulator)
    make_button(row2, "Movement", app.open_movement_screen)
    make_button(row2, "Export", app.open_export)
    make_button(row2, "Settings", app.open_settings)

    return toolbar
