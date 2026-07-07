"""Envelope Probabilities panel: per-card horizontal bars (not just the single
best guess) showing each card's probability of being the envelope card, for
each of Suspect/Weapon/Room.

Mirrors main_screen.py's existing try/except around `TooManyAmbiguousCardsError`
-- when too many cards are still ambiguous for an exact count, this shows a
plain "not enough information yet" message instead of guessing.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.models import ENVELOPE, CardType
from cluedo.probability import TooManyAmbiguousCardsError

_BAR_WIDTH = 140
_BAR_HEIGHT = 12

_CATEGORY_TITLES = (
    (CardType.SUSPECT, "Suspect"),
    (CardType.WEAPON, "Weapon"),
    (CardType.ROOM, "Room"),
)


def build(parent, theme) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    box = tk.LabelFrame(frame, text="Envelope Probabilities", font=theme.body_font(11), bg=theme.panel_bg)
    box.pack(fill="x")

    body = tk.Frame(box, bg=theme.panel_bg)
    body.pack(fill="x", padx=8, pady=8)

    def _bar_color(p: float) -> str:
        if p >= 0.999:
            return theme.confirmed
        return theme.accent

    def _render_row(container, name: str, p: float) -> None:
        row = tk.Frame(container, bg=theme.panel_bg)
        row.pack(fill="x", pady=1)
        tk.Label(
            row, text=name, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9), width=16, anchor="w",
        ).pack(side="left")
        canvas = tk.Canvas(row, width=_BAR_WIDTH, height=_BAR_HEIGHT, bg=theme.unknown, highlightthickness=0)
        canvas.pack(side="left", padx=(4, 6))
        canvas.create_rectangle(0, 0, _BAR_WIDTH * max(0.0, min(1.0, p)), _BAR_HEIGHT, fill=_bar_color(p), width=0)
        tk.Label(
            row, text=f"{p * 100:.0f}%", bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9), width=5,
        ).pack(side="left")

    def refresh(game_state):
        for child in body.winfo_children():
            child.destroy()

        if game_state is None:
            tk.Label(
                body, text="No game in progress.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        try:
            probs = game_state.card_probabilities()
        except TooManyAmbiguousCardsError:
            tk.Label(
                body, text="Not enough information yet for probabilities.",
                bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9),
                wraplength=280, justify="left",
            ).pack(anchor="w")
            return

        for card_type, title in _CATEGORY_TITLES:
            section = tk.Frame(body, bg=theme.panel_bg)
            section.pack(fill="x", pady=(4, 2))
            tk.Label(
                section, text=title, bg=theme.panel_bg, fg=theme.accent_dark,
                font=theme.body_font(10, "bold"),
            ).pack(anchor="w")

            cards = [c for c in game_state.cards if c.type == card_type]
            cards.sort(key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), reverse=True)
            for card in cards:
                p = probs.get(card, {}).get(ENVELOPE, 0.0)
                _render_row(section, card.name, p)

    frame.refresh = refresh
    refresh(None)
    return frame
