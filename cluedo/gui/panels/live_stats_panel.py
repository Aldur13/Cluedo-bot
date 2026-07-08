"""Live Solver Statistics card: surfaces `cluedo.analysis.live_stats.
LiveStats` -- confidence tier + explanation, remaining worlds,
confirmed/unknown card counts, entropy, an expected-turns-to-solve estimate
(clearly labeled as such), and probability stability. Styled like the other
advisory-but-derived cards (accent heading), since several of these fields
are honest estimates over exact solver output, not exact facts themselves.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.live_stats import compute_live_stats
from cluedo.gui.widgets import CollapsibleCard


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(
        frame, theme, title="Live Stats", key="live_stats", fg=theme.accent_dark,
        disclaimer="Expected-turns-to-solve is an estimate; everything else is exact.",
    )
    card.pack(fill="x")
    body = card.body

    info_label = tk.Label(
        body, text="", justify="left", wraplength=280, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
    )
    info_label.pack(anchor="w")

    def refresh(game_state):
        if game_state is None:
            info_label.config(text="No game in progress.", fg=theme.muted_text)
            return

        stats = compute_live_stats(game_state)
        worlds_text = "unknown" if stats.remaining_valid_worlds is None else f"{stats.remaining_valid_worlds:,}"
        entropy_text = "N/A" if stats.entropy_bits is None else f"{stats.entropy_bits:.1f} bits"
        turns_text = "N/A" if stats.expected_turns_to_solve is None else f"~{stats.expected_turns_to_solve:.1f}"
        stability_text = "N/A" if stats.probability_stability is None else f"{stats.probability_stability * 100:.0f}%"

        info_label.config(
            fg=theme.text,
            text=(
                f"Confidence: {stats.confidence_tier}\n"
                f"{stats.confidence_explanation}\n"
                f"Remaining worlds: {worlds_text}\n"
                f"Confirmed: {stats.confirmed_cards}   Unknown: {stats.unknown_cards}\n"
                f"Entropy: {entropy_text}\n"
                f"Estimated turns to solve: {turns_text}\n"
                f"Probability stability: {stability_text}"
            ),
        )

    frame.refresh = refresh
    refresh(None)
    return frame
