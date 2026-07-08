"""Recommendation Simulator: shows every possible response to a candidate
suggestion before it's made -- one row per `advisor.OutcomeBreakdown`
(already computed by `advisor.rank_candidates_detailed`, just not
previously surfaced). Each row shows who would respond (or "Nobody
shows"), that outcome's real probability, the resulting world count, and
the resulting confidence tier (reusing `cluedo.analysis.live_stats.
confidence_tier`, the same tiering the sidebar/Live Stats use).
"""
from __future__ import annotations

import tkinter as tk

from cluedo.advisor import rank_candidates_detailed
from cluedo.analysis.live_stats import confidence_tier


def open_recommendation_simulator(app, detailed_candidate=None):
    gs = app.game_state
    theme = app.theme_manager.current

    if detailed_candidate is None:
        top = rank_candidates_detailed(gs, top_k=1)
        detailed_candidate = top[0] if top else None

    win = tk.Toplevel(app.root)
    win.title("Recommendation Simulator")
    win.geometry("560x520")
    win.configure(bg=theme.bg)

    tk.Label(
        win, text="Recommendation Simulator", font=theme.heading_font(16), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(14, 6))

    if detailed_candidate is None:
        tk.Label(
            win, text="No candidate suggestion available to simulate (game may already be solved).",
            bg=theme.bg, fg=theme.muted_text, font=theme.body_font(10),
        ).pack(anchor="w", padx=16, pady=12)
        tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
        return

    c = detailed_candidate.candidate
    tk.Label(
        win, text=f"{c.suspect.name} · {c.weapon.name} · {c.room.name}", font=theme.body_font(12, "bold"),
        bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(0, 8))

    list_area = tk.Frame(win, bg=theme.bg)
    list_area.pack(fill="both", expand=True, padx=16)

    if not detailed_candidate.outcomes:
        tk.Label(
            list_area, text="Too many cards are still ambiguous to simulate outcomes exactly.",
            bg=theme.bg, fg=theme.muted_text, font=theme.body_font(9),
        ).pack(anchor="w")

    for outcome in detailed_candidate.outcomes:
        row = tk.Frame(list_area, bg=theme.panel_bg, highlightbackground=theme.unknown, highlightthickness=1)
        row.pack(fill="x", pady=3)
        body = tk.Frame(row, bg=theme.panel_bg)
        body.pack(fill="x", padx=10, pady=8)

        if outcome.responder is None:
            who = "If nobody shows:"
        else:
            player = next((p for p in gs.players if p.seat_index == outcome.responder), None)
            who = f"If {player.name if player else f'seat {outcome.responder}'} shows:"
        tk.Label(body, text=who, font=theme.body_font(10, "bold"), bg=theme.panel_bg, fg=theme.text).pack(anchor="w")

        tk.Label(
            body, text=f"Probability: {outcome.probability * 100:.0f}%", font=theme.body_font(9),
            bg=theme.panel_bg, fg=theme.text,
        ).pack(anchor="w")
        tk.Label(
            body, text=f"Worlds remaining: {outcome.worlds_remaining:,}", font=theme.body_font(9),
            bg=theme.panel_bg, fg=theme.text,
        ).pack(anchor="w")

        tier, _explanation = confidence_tier(outcome.worlds_remaining, is_solved=outcome.worlds_remaining <= 1)
        tk.Label(
            body, text=f"Resulting confidence: {tier}", font=theme.body_font(9),
            bg=theme.panel_bg, fg=theme.confirmed if tier == "Certain" else theme.muted_text,
        ).pack(anchor="w")

        if outcome.category_collapses:
            names = ", ".join(ct.value for ct in outcome.category_collapses)
            tk.Label(
                body, text=f"Likely solved: {names}", font=theme.body_font(9), bg=theme.panel_bg, fg=theme.accent,
            ).pack(anchor="w")

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
