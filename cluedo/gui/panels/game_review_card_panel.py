"""Game Review card: a sidebar summary of `cluedo.analysis.game_review.
GameReview`, populated once a game is solved. Reads `app._game_review_cache`
(set once by App._maybe_auto_open_review, the same place that drives the
auto-open popup) rather than recomputing -- GameReview is expensive, so this
card and the popup share one computation, never two.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.gui.widgets import CollapsibleCard

_CARD_KEY = "game_review"


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Game Review", key=_CARD_KEY)
    card.pack(fill="x")
    body = card.body

    message_label = tk.Label(
        body, text="", justify="left", wraplength=280, bg=theme.panel_bg, fg=theme.muted_text,
        font=theme.body_font(9),
    )
    message_label.pack(anchor="w")

    stats_label = tk.Label(
        body, text="", justify="left", wraplength=280, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
    )

    open_button = tk.Button(body, text="Open Full Review", font=theme.body_font(9), command=app.open_game_review)

    def refresh(game_state):
        stats_label.pack_forget()
        open_button.pack_forget()

        if game_state is None or not game_state.is_solved():
            message_label.config(text="Available once the mystery is solved.")
            message_label.pack(anchor="w")
            return

        review = getattr(app, "_game_review_cache", None)
        if review is None:
            message_label.config(text="Solved — review not yet computed.")
            message_label.pack(anchor="w")
            return

        message_label.pack_forget()
        lines = [
            f"Grade: {review.overall_rating or 'N/A'}",
            f"Efficiency: {'N/A' if review.efficiency_pct is None else f'{review.efficiency_pct:.0f}%'}",
            f"Difficulty: {review.difficulty}",
        ]
        if review.key_turning_point is not None:
            lines.append(f"Best Turn: {review.key_turning_point.turn}")
        if review.largest_deduction is not None:
            card_name = f" — {review.largest_deduction.card.name}" if review.largest_deduction.card else ""
            lines.append(f"Largest Deduction: Turn {review.largest_deduction.turn}{card_name}")
        lines.append(f"Missed Opportunities: {len(review.missed_opportunities)}")
        stats_label.config(text="\n".join(lines))
        stats_label.pack(anchor="w")
        open_button.pack(anchor="w", pady=(6, 0))

    frame.refresh = refresh
    refresh(None)
    return frame
