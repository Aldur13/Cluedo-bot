"""Timeline panel: major events only -- turns that produced a new confirmed
card (cluedo.analysis.live_events), plus the solving turn -- as opposed to
every single suggestion (see cluedo.gui.timeline_screen for the full log).
Clicking a row jumps into Replay at that turn.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.live_events import confirmed_card_events
from cluedo.gui import replay_screen
from cluedo.gui.widgets import CollapsibleCard

_CARD_KEY = "timeline"


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Timeline", key=_CARD_KEY)
    card.pack(fill="x")
    body = card.body

    rows_frame = tk.Frame(body, bg=theme.panel_bg)
    rows_frame.pack(fill="x")

    def _open_at(turn: int):
        if app.game_state is not None:
            replay_screen.open_replay(app, initial_index=turn)

    def _major_events(game_state):
        """One row per turn with new confirmations (cards it confirmed,
        for the label), plus a final SOLVED row if applicable -- never a
        row for a turn that revealed nothing."""
        events = confirmed_card_events(game_state)
        by_turn: dict[int, list] = {}
        for event in events:
            by_turn.setdefault(event.turn, []).append(event)
        rows = [
            (turn, f"Turn {turn}: {', '.join(e.card.name for e in turn_events)} confirmed")
            for turn, turn_events in sorted(by_turn.items())
        ]
        if game_state.is_solved():
            solve_turn = len(game_state.history)
            suspect, weapon, room = game_state.solution()
            rows.append((solve_turn, f"Turn {solve_turn}: SOLVED — {suspect.name} · {weapon.name} · {room.name}"))
        return rows

    def refresh(game_state):
        for child in rows_frame.winfo_children():
            child.destroy()

        if game_state is None:
            tk.Label(
                rows_frame, text="No game in progress.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        rows = _major_events(game_state)
        if not rows:
            empty_text = "No suggestions logged yet." if not game_state.history else "No major events yet."
            tk.Label(
                rows_frame, text=empty_text, bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9),
            ).pack(anchor="w")
            return

        for turn, label in rows:
            btn = tk.Button(
                rows_frame, text=label, font=theme.body_font(8), anchor="w", justify="left",
                relief="flat", bg=theme.panel_bg, fg=theme.accent_dark, wraplength=280,
                command=lambda t=turn: _open_at(t),
            )
            btn.pack(fill="x", anchor="w", pady=1)

    frame.refresh = refresh
    refresh(None)
    return frame
