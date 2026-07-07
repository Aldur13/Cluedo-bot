"""Recent Deductions panel: lists cards that were newly confirmed by real
suggestion outcomes, most recent turn first -- every row is a genuine
solver fact (cluedo.analysis.live_events.confirmed_card_events), never a
prediction. Capped to the 5 most recent by default, with "Show All" to see
the whole game.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.live_events import confirmed_card_events, owner_display_name
from cluedo.gui import sidebar_state
from cluedo.gui.widgets import CollapsibleCard

_CARD_KEY = "recent_deductions"
_SHOW_ALL_KEY = "recent_deductions.show_all"
_TOP_N_DEFAULT = 5


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Recent Deductions", key=_CARD_KEY)
    card.pack(fill="x")
    body = card.body

    rows_frame = tk.Frame(body, bg=theme.panel_bg)
    rows_frame.pack(fill="x")

    show_all_button = tk.Button(body, text="Show All", font=theme.body_font(8))

    def _one_liner(game_state, event) -> str:
        owner = owner_display_name(game_state, event.owner_id)
        explanation = game_state.explain_card(event.card)
        if explanation is not None and explanation.narrative:
            return explanation.narrative[-1]
        return f"{event.card.name} confirmed as {owner}'s."

    def _render(game_state, events, show_all):
        for child in rows_frame.winfo_children():
            child.destroy()
        show_all_button.pack_forget()

        if not events:
            tk.Label(
                rows_frame, text="No deductions yet.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        most_recent_first = list(reversed(events))
        visible = most_recent_first if show_all else most_recent_first[:_TOP_N_DEFAULT]
        for event in visible:
            row = tk.Frame(rows_frame, bg=theme.panel_bg)
            row.pack(fill="x", anchor="w", pady=2)
            tk.Label(
                row, text=f"Turn {event.turn}: {event.card.name}", bg=theme.panel_bg, fg=theme.text,
                font=theme.body_font(9, "bold"), anchor="w", justify="left",
            ).pack(anchor="w")
            tk.Label(
                row, text=_one_liner(game_state, event), bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(8), anchor="w", justify="left", wraplength=280,
            ).pack(anchor="w")

        if len(most_recent_first) > _TOP_N_DEFAULT:
            show_all_button.config(
                text="Show Less" if show_all else f"Show All ({len(most_recent_first)})",
                command=lambda: _toggle_show_all(game_state, events),
            )
            show_all_button.pack(anchor="w", pady=(4, 0))

    def _toggle_show_all(game_state, events):
        show_all = sidebar_state.toggle_flag(_SHOW_ALL_KEY, False)
        _render(game_state, events, show_all)

    def refresh(game_state):
        if game_state is None:
            _render(None, [], False)
            return
        events = confirmed_card_events(game_state)
        _render(game_state, events, sidebar_state.get_flag(_SHOW_ALL_KEY, False))

    frame.refresh = refresh
    refresh(None)
    return frame
