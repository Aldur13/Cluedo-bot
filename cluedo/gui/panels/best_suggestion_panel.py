"""Best Suggestion panel: the advisor's #1 recommendation, dressed up with a
star-rating-style confidence indicator derived from `expected_info_gain`.

`expected_info_gain` is only exact when the engine's ambiguous-card count is
small enough (see advisor.py's `_MAX_AMBIGUOUS_FOR_EXACT_GAIN` gate); above
that threshold `AdvisorCandidate.expected_info_gain` is `None` and the
advisor falls back to a cheap uncertainty ranking. This panel never shows a
bogus "None%" -- when the gain is unavailable it says so plainly and omits
the star bar entirely, per the plan's product-honesty requirement.

"Show Why" reveals `AdvisorCandidate.rationale` -- already computed by the
advisor, just not previously surfaced in this panel. No new metric is
invented for this: `expected_info_gain` is the one real number the advisor
produces, so it is the only confidence figure shown.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.gui import sidebar_state
from cluedo.gui.widgets import CollapsibleCard

_STAR_COUNT = 5
_FILLED_STAR = "★"  # ★
_EMPTY_STAR = "☆"  # ☆
_CARD_KEY = "best_suggestion"
_SHOW_WHY_KEY = "best_suggestion.show_why"


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Best Suggestion", key=_CARD_KEY)
    card.pack(fill="x")
    body = card.body

    solved_label = tk.Label(
        body, text="", justify="left", wraplength=290, bg=theme.solved_bg, fg=theme.solved_text,
        font=theme.heading_font(11), padx=8, pady=6,
    )

    empty_label = tk.Label(
        body, text="Not enough information yet to suggest anything.",
        justify="left", wraplength=290, bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(10),
    )

    triple_label = tk.Label(
        body, text="", justify="left", wraplength=290, bg=theme.panel_bg, fg=theme.text,
        font=theme.body_font(11, "bold"),
    )

    confidence_frame = tk.Frame(body, bg=theme.panel_bg)
    stars_label = tk.Label(confidence_frame, text="", bg=theme.panel_bg, fg=theme.accent, font=("Segoe UI", 14))
    confidence_text = tk.Label(
        confidence_frame, text="", bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9)
    )

    show_why_button = tk.Button(body, text="Show Why", font=theme.body_font(8))
    rationale_label = tk.Label(
        body, text="", justify="left", wraplength=290, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
    )

    state = {"rationale": ""}

    def _clear():
        for widget in (solved_label, empty_label, triple_label, confidence_frame, show_why_button, rationale_label):
            widget.pack_forget()

    def _apply_show_why():
        expanded = sidebar_state.get_flag(_SHOW_WHY_KEY)
        show_why_button.config(text="Hide Why" if expanded else "Show Why")
        if expanded:
            # Only set real text while actually shown -- a hidden
            # (pack_forget'd) Label is still present in the widget tree, so
            # leaving real text on it would let a naive text-walk over the
            # tree "see" content the user can't.
            rationale_label.config(text=state["rationale"])
            rationale_label.pack(anchor="w")
        else:
            rationale_label.config(text="")
            rationale_label.pack_forget()

    def _on_toggle_why():
        sidebar_state.toggle_flag(_SHOW_WHY_KEY)
        _apply_show_why()

    show_why_button.config(command=_on_toggle_why)

    def refresh(game_state):
        _clear()

        if game_state is None:
            empty_label.pack(anchor="w")
            return

        if game_state.is_solved():
            suspect, weapon, room = game_state.solution()
            solved_label.config(text=f"SOLVED — {suspect.name} · {weapon.name} · {room.name}")
            solved_label.pack(fill="x")
            return

        candidates = game_state.best_suggestions(top_k=5)
        if not candidates:
            empty_label.pack(anchor="w")
            return

        best = candidates[0]
        triple_label.config(
            text=f"Suspect: {best.suspect.name}\nWeapon: {best.weapon.name}\nRoom: {best.room.name}"
        )
        triple_label.pack(anchor="w", pady=(0, 6))

        gain = best.expected_info_gain
        if gain is None:
            stars_label.config(text="")
            confidence_text.config(text="Ranked by uncertainty (exact odds unavailable yet)")
        else:
            gain = max(0.0, min(1.0, gain))
            filled = round(gain * _STAR_COUNT)
            stars_label.config(text=_FILLED_STAR * filled + _EMPTY_STAR * (_STAR_COUNT - filled))
            confidence_text.config(text=f"Expected info gain: {gain * 100:.0f}%")
        stars_label.pack(anchor="w")
        confidence_text.pack(anchor="w")
        confidence_frame.pack(fill="x", pady=(0, 6))

        state["rationale"] = best.rationale
        show_why_button.pack(anchor="w", pady=(0, 4))
        _apply_show_why()

    frame.refresh = refresh
    refresh(None)
    return frame
