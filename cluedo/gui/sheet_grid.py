"""Shared detective-sheet grid renderer. Extracted and upgraded from the
inline grid that used to live in main_screen.py, so the dashboard (Phase 3),
replay, and what-if screens (Phase 4) all render the sheet through this one
function instead of three divergent copies.

Upgrades over the original inline version:
- bigger cells (wider, taller padding, larger font) for legibility
- a distinct icon/glyph per status instead of a bare check/question/cross
  (kept as Unicode symbols, same characters as before, just styled larger)
- a themed "recently changed" highlight (a colored border using
  `theme.accent`) driven by `cluedo.change_tracking.compute_last_changed_turns`
- a richer hover tooltip: probability (when computable), the explanation
  narrative, and the last-changed turn number
"""
from __future__ import annotations

import tkinter as tk

from cluedo.change_tracking import compute_last_changed_turns
from cluedo.gui.widgets import Tooltip
from cluedo.models import CardType, ENVELOPE
from cluedo.probability import TooManyAmbiguousCardsError

# Border thickness applied (via highlightthickness/highlightbackground, which
# plain tk.Label widgets support even though they aren't interactive) to a
# cell whose card most-recently changed. Kept as module constants so tests
# can assert on the exact values without hardcoding magic numbers twice.
HIGHLIGHT_BORDER_THICKNESS = 3
NORMAL_BORDER_THICKNESS = 0

_STATUS_ICONS = {
    "confirmed": "✔",  # ✔
    "possible": "?",
    "impossible": "✘",  # ✘
}


def _cell_status(info: dict, owner) -> str:
    if info["status"] == "confirmed" and info["owner"] == owner:
        return "confirmed"
    if owner in info["possible"]:
        return "possible"
    return "impossible"


def render_sheet_grid(parent, game_state, theme, on_cell_click=None) -> tk.Frame:
    """Builds a scrollable grid (Canvas + Scrollbar + inner Frame, same
    pattern the old main_screen.py grid used) showing every card's
    confirmed/possible/impossible status per player + the envelope.

    `on_cell_click`, if given, is called with the clicked `Card` when a cell
    is clicked. If None (the default), the grid is read-only/non-interactive
    -- e.g. for a replay/what-if view that shouldn't trigger the live
    explain-dialog flow.

    Must render correctly for both a fresh unsolved game (no history yet, so
    every card is "last changed at turn 0") and a solved game (every card
    confirmed).
    """
    container = tk.Frame(parent, bg=theme.panel_bg, bd=1, relief="solid")

    canvas = tk.Canvas(container, bg=theme.panel_bg, highlightthickness=0)
    vscroll = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    sheet_frame = tk.Frame(canvas, bg=theme.panel_bg)
    canvas.create_window((0, 0), window=sheet_frame, anchor="nw")
    sheet_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    sheet = game_state.detective_sheet()
    owners = [p.owner_id for p in game_state.players] + [ENVELOPE]
    owner_labels = [p.name for p in game_state.players] + ["Envelope"]

    last_changed = compute_last_changed_turns(game_state)
    # "Recently changed" = changed on the most recent suggestion. With no
    # suggestions logged yet, every card sits at turn 0 trivially -- that's
    # the initial-hand snapshot, not a "recent change", so nothing is
    # highlighted on a fresh game.
    current_turn = len(game_state.history)

    def is_recently_changed(card) -> bool:
        return current_turn > 0 and last_changed.get(card) == current_turn

    tk.Label(sheet_frame, text="", bg=theme.panel_bg, width=20).grid(row=0, column=0)
    for c, label in enumerate(owner_labels, start=1):
        tk.Label(
            sheet_frame, text=label, font=theme.body_font(11, "bold"), bg=theme.panel_bg, fg=theme.text
        ).grid(row=0, column=c, padx=3, pady=3)

    row = 1
    for card_type in (CardType.SUSPECT, CardType.WEAPON, CardType.ROOM):
        tk.Label(
            sheet_frame, text=card_type.value.title(), font=theme.body_font(12, "bold"),
            bg=theme.panel_bg, fg=theme.accent_dark,
        ).grid(row=row, column=0, columnspan=len(owners) + 1, sticky="w", pady=(14, 3), padx=6)
        row += 1
        for card in game_state.cards:
            if card.type != card_type:
                continue
            info = sheet[card]
            recently_changed = is_recently_changed(card)
            tk.Label(
                sheet_frame, text=card.name, font=theme.body_font(11), bg=theme.panel_bg, fg=theme.text,
                anchor="w", width=20,
            ).grid(row=row, column=0, sticky="w", padx=6)
            for c, owner in enumerate(owners, start=1):
                status = _cell_status(info, owner)
                if status == "confirmed":
                    bg = theme.confirmed
                elif status == "possible":
                    bg = theme.possible
                else:
                    bg = theme.impossible
                icon = _STATUS_ICONS[status]

                cell = tk.Label(
                    sheet_frame, text=icon, bg=bg, width=6, font=theme.body_font(13, "bold"), padx=6, pady=8,
                    highlightthickness=HIGHLIGHT_BORDER_THICKNESS if recently_changed else NORMAL_BORDER_THICKNESS,
                    highlightbackground=theme.accent, highlightcolor=theme.accent,
                )
                cell.grid(row=row, column=c, padx=2, pady=2, sticky="nsew")

                # Testable markers, independent of the visual-only highlight
                # options above (plain python-attribute assignment on a
                # tkinter widget instance is fine -- it's just an object).
                cell.cluedo_card = card
                cell.cluedo_recently_changed = recently_changed

                if on_cell_click is not None:
                    cell.bind("<Button-1>", lambda e, card=card: on_cell_click(card))

                def tooltip_text(card=card, owner=owner):
                    return _tooltip_text(game_state, card, owner, last_changed)

                Tooltip(cell, tooltip_text, theme=theme)
            row += 1

    return container


def _tooltip_text(game_state, card, owner, last_changed: dict) -> str:
    info = game_state.detective_sheet()[card]
    lines = []

    if info["status"] == "confirmed":
        lines.append(f"Confirmed: {info['owner']}")
    else:
        lines.append("Still possible: " + ", ".join(sorted(info["possible"])))

    try:
        probs = game_state.card_probabilities()
        p = probs.get(card, {}).get(owner)
        if p is not None:
            lines.append(f"P({owner} holds this): {p * 100:.0f}%")
    except TooManyAmbiguousCardsError:
        lines.append("Probability: not enough information yet.")

    explanation = game_state.explain_card(card)
    if explanation is not None:
        lines.append("")
        lines.extend(explanation.narrative)

    turn = last_changed.get(card)
    if turn is not None:
        lines.append("")
        lines.append("Last changed: initial hand" if turn == 0 else f"Last changed: turn {turn}")

    return "\n".join(lines)
