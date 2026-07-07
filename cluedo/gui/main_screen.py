import tkinter as tk

from cluedo.gui.panels import (
    ai_insights_panel,
    best_suggestion_panel,
    endgame_panel,
    envelope_probabilities_panel,
    game_statistics_panel,
    mystery_progress_panel,
)
from cluedo.gui.sheet_grid import render_sheet_grid
from cluedo.gui.toolbar import build_toolbar

# Dashboard side-panel order, top to bottom -- matches the named sections in
# the product spec (Best Suggestion, Mystery Progress, Envelope
# Probabilities, AI Insights, Statistics), plus Endgame slotted alongside the
# other advisory (non-solver-fact) panels.
_SIDE_PANEL_MODULES = (
    best_suggestion_panel,
    mystery_progress_panel,
    envelope_probabilities_panel,
    ai_insights_panel,
    endgame_panel,
    game_statistics_panel,
)


def build(parent, app):
    """`app` is the App controller; this screen reads/writes app.game_state and
    calls back into `app` for cross-screen actions (dialogs, save, etc.)."""
    theme = app.theme_manager.current
    frame = tk.Frame(parent, bg=theme.bg)

    header = tk.Frame(frame, bg=theme.bg)
    header.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(header, text="Detective Sheet", font=theme.heading_font(16), bg=theme.bg, fg=theme.text).pack(
        side="left"
    )
    banner = tk.Label(
        header, text="", font=theme.heading_font(13), bg=theme.solved_bg, fg=theme.solved_text, padx=10, pady=4
    )

    toolbar = build_toolbar(frame, app, theme)
    toolbar.pack(fill="x", padx=12, pady=(0, 8))

    body = tk.Frame(frame, bg=theme.bg)
    body.pack(fill="both", expand=True, padx=12, pady=4)

    sheet_container_holder = tk.Frame(body, bg=theme.bg)
    sheet_container_holder.pack(side="left", fill="both", expand=True, padx=(0, 8))

    side_panel = tk.Frame(body, bg=theme.bg, width=320)
    side_panel.pack(side="left", fill="y")
    side_panel.pack_propagate(False)

    panels = []
    for module in _SIDE_PANEL_MODULES:
        panel_frame = module.build(side_panel, theme)
        panel_frame.pack(fill="x", pady=(0, 8))
        panels.append(panel_frame)

    def refresh():
        gs = app.game_state
        if gs is None:
            return
        for child in sheet_container_holder.winfo_children():
            child.destroy()
        sheet_container = render_sheet_grid(sheet_container_holder, gs, theme, on_cell_click=app.open_explain)
        sheet_container.pack(fill="both", expand=True)

        if gs.is_solved():
            suspect, weapon, room = gs.solution()
            banner.config(text=f"SOLVED — {suspect.name} · {weapon.name} · {room.name}")
            banner.pack(side="right")
        else:
            banner.pack_forget()

        for panel_frame in panels:
            panel_frame.refresh(gs)

    app.refresh_main_screen = refresh
    refresh()
    return frame
