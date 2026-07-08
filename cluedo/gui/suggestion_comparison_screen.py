"""Suggestion Comparison: ranks the top candidate suggestions side by side
(not just the single best one `best_suggestion_panel.py` shows), each with
a star rating, expected info gain / world reduction (the same exact metric
`advisor.py` already computes -- "world reduction" is just that same
fraction under its other name, not a second invented number), an expected
deduction count (real: the number of card categories that collapse to one
candidate in that suggestion's single most likely outcome), and a
confidence label. Two candidates can be checked for a side-by-side view.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.advisor import rank_candidates_detailed
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.window_geometry import fit_geometry

_STAR_COUNT = 5
_FILLED_STAR = "★"  # ★
_EMPTY_STAR = "☆"  # ☆


def _stars(gain) -> str:
    if gain is None:
        return _EMPTY_STAR * _STAR_COUNT
    filled = round(max(0.0, min(1.0, gain)) * _STAR_COUNT)
    return _FILLED_STAR * filled + _EMPTY_STAR * (_STAR_COUNT - filled)


def _expected_deduction_count(detailed) -> int:
    if not detailed.outcomes:
        return 0
    best_outcome = max(detailed.outcomes, key=lambda o: o.probability)
    return len(best_outcome.category_collapses)


def open_suggestion_comparison(app):
    gs = app.game_state
    theme = app.theme_manager.current

    win = tk.Toplevel(app.root)
    win.title("Suggestion Comparison")
    fit_geometry(win, 700, 600)
    win.configure(bg=theme.bg)

    # Packed first, side="bottom", so Close stays reachable regardless of
    # how many candidate rows the scrollable list below grows to.
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="bottom", pady=(0, 10))

    tk.Label(
        win, text="Suggestion Comparison", font=theme.heading_font(16), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(14, 6))

    detailed_candidates = rank_candidates_detailed(gs, top_k=5)

    if not detailed_candidates:
        tk.Label(
            win, text="No candidate suggestions available (game may already be solved).",
            bg=theme.bg, fg=theme.muted_text, font=theme.body_font(10),
        ).pack(anchor="w", padx=16, pady=12)
        return

    # Also packed side="bottom" (before the scrollable list below), so the
    # comparison panel stays reachable too instead of being starved of
    # space by the list's fill="both", expand=True claim.
    compare_area = tk.Frame(win, bg=theme.bg)
    compare_area.pack(side="bottom", fill="x", padx=16, pady=(0, 10))

    scroll_outer, list_area = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

    selected = []
    check_vars = []

    def _on_check(index, var):
        if var.get():
            if index not in selected:
                selected.append(index)
        else:
            if index in selected:
                selected.remove(index)
        while len(selected) > 2:
            dropped = selected.pop(0)
            check_vars[dropped].set(False)
        _render_compare()

    def _render_compare():
        for child in compare_area.winfo_children():
            child.destroy()
        if len(selected) != 2:
            tk.Label(
                compare_area, text="Select exactly two suggestions above to compare side by side.",
                bg=theme.bg, fg=theme.muted_text, font=theme.body_font(9),
            ).pack(anchor="w")
            return

        columns = tk.Frame(compare_area, bg=theme.bg)
        columns.pack(fill="x")
        for index in selected:
            dc = detailed_candidates[index]
            c = dc.candidate
            col = tk.Frame(columns, bg=theme.panel_bg, highlightbackground=theme.unknown, highlightthickness=1)
            col.pack(side="left", fill="both", expand=True, padx=4)
            body = tk.Frame(col, bg=theme.panel_bg)
            body.pack(fill="both", padx=8, pady=8)
            tk.Label(
                body, text=f"{c.suspect.name} · {c.weapon.name} · {c.room.name}", font=theme.body_font(10, "bold"),
                bg=theme.panel_bg, fg=theme.text, wraplength=280, justify="left",
            ).pack(anchor="w")
            gain_text = "N/A" if c.expected_info_gain is None else f"{c.expected_info_gain * 100:.0f}%"
            tk.Label(
                body, text=f"Info gain / world reduction: {gain_text}", font=theme.body_font(9),
                bg=theme.panel_bg, fg=theme.text,
            ).pack(anchor="w", pady=(4, 0))
            tk.Label(
                body, text=f"Expected deductions: {_expected_deduction_count(dc)}", font=theme.body_font(9),
                bg=theme.panel_bg, fg=theme.text,
            ).pack(anchor="w")
            tk.Label(
                body, text=c.rationale, font=theme.body_font(8), bg=theme.panel_bg, fg=theme.muted_text,
                wraplength=280, justify="left",
            ).pack(anchor="w", pady=(4, 0))

    for i, dc in enumerate(detailed_candidates):
        c = dc.candidate
        row = tk.Frame(list_area, bg=theme.panel_bg, highlightbackground=theme.unknown, highlightthickness=1)
        row.pack(fill="x", pady=3)
        body = tk.Frame(row, bg=theme.panel_bg)
        body.pack(fill="x", padx=8, pady=6)

        var = tk.BooleanVar(value=False)
        check_vars.append(var)
        tk.Checkbutton(
            body, variable=var, bg=theme.panel_bg, command=lambda i=i, v=var: _on_check(i, v),
        ).pack(side="left")

        text_col = tk.Frame(body, bg=theme.panel_bg)
        text_col.pack(side="left", fill="x", expand=True)
        tk.Label(
            text_col, text=_stars(c.expected_info_gain), bg=theme.panel_bg, fg=theme.accent, font=("Segoe UI", 13),
        ).pack(anchor="w")
        tk.Label(
            text_col, text=f"{c.suspect.name} · {c.weapon.name} · {c.room.name}", font=theme.body_font(10, "bold"),
            bg=theme.panel_bg, fg=theme.text,
        ).pack(anchor="w")
        gain_text = "N/A" if c.expected_info_gain is None else f"{c.expected_info_gain * 100:.0f}%"
        confidence = "Exact" if c.expected_info_gain is not None else "Estimated (rough ranking only)"
        tk.Label(
            text_col,
            text=(
                f"Info gain / world reduction: {gain_text}   "
                f"Expected deductions: {_expected_deduction_count(dc)}   "
                f"Confidence: {confidence}"
            ),
            font=theme.body_font(9), bg=theme.panel_bg, fg=theme.muted_text,
        ).pack(anchor="w")
        tk.Label(
            text_col, text=c.rationale, font=theme.body_font(8), bg=theme.panel_bg, fg=theme.muted_text,
            wraplength=520, justify="left",
        ).pack(anchor="w")

    _render_compare()
