"""Best Suggestion panel: the advisor's #1 recommendation, dressed up with a
star-rating-style confidence indicator derived from `expected_info_gain`.

`expected_info_gain` is only exact when the engine's ambiguous-card count is
small enough (see advisor.py's `_MAX_AMBIGUOUS_FOR_EXACT_GAIN` gate); above
that threshold `AdvisorCandidate.expected_info_gain` is `None` and the
advisor falls back to a cheap uncertainty ranking. This panel never shows a
bogus "None%" -- when the gain is unavailable it says so plainly and omits
the star bar entirely, per the plan's product-honesty requirement.
"""
from __future__ import annotations

import tkinter as tk

_STAR_COUNT = 5
_FILLED_STAR = "★"  # ★
_EMPTY_STAR = "☆"  # ☆


def build(parent, theme) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    box = tk.LabelFrame(frame, text="Best Suggestion", font=theme.body_font(11), bg=theme.panel_bg)
    box.pack(fill="x")

    body = tk.Frame(box, bg=theme.panel_bg)
    body.pack(fill="x", padx=8, pady=8)

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

    rationale_label = tk.Label(
        body, text="", justify="left", wraplength=290, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
    )

    def _clear():
        for widget in (solved_label, empty_label, triple_label, confidence_frame, rationale_label):
            widget.pack_forget()

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

        rationale_label.config(text=best.rationale)
        rationale_label.pack(anchor="w")

    frame.refresh = refresh
    refresh(None)
    return frame
