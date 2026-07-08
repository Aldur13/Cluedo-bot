"""Explain dialog: click any confirmed card to see the full logical
derivation chain that confirmed it, not just its top-level fact -- rendered
as a linear arrow chain (`full_derivation_chain`, already exact, DFS order:
conclusion first, down through the facts that forced it). For a card whose
derivation branches (a fact with more than one premise, each with its own
sub-derivation), "Open Deduction Graph" opens the full expandable tree view.
Never invents reasoning -- every line is a real `Fact.label` already
recorded by the engine's `ExplanationRegistry`.
"""
import tkinter as tk

from cluedo.explain import full_derivation_chain
from cluedo.gui import deduction_graph_screen
from cluedo.gui.window_geometry import fit_geometry


def open_explain(app, card):
    gs = app.game_state
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title(f"Why: {card.name}")
    fit_geometry(win, 460, 420)
    win.configure(bg=theme.bg)

    # Packed first, side="bottom", so Close (and the optional graph button
    # below) stay reachable regardless of how long the derivation text gets
    # -- the label below is the one widget that expands to fill leftover
    # space, and packing it after these means it can never crowd them out.
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="bottom", pady=(0, 12))

    explanation = gs.explain_card(card)
    show_graph_button = False
    if explanation is None:
        info = gs.detective_sheet()[card]
        text = f"{card.name} is not yet confirmed.\n\nStill possible: {', '.join(sorted(info['possible']))}"
    else:
        chain = full_derivation_chain(explanation, gs.engine.explanations)
        lines = [f"{card.name} confirmed"]
        for exp in chain:
            lines.append("↓")
            lines.append(exp.conclusion.label)
        text = "\n".join(lines)
        show_graph_button = any(len(exp.premises) > 1 for exp in chain)

    if show_graph_button:
        tk.Button(
            win, text="Open Deduction Graph", font=theme.body_font(9),
            command=lambda: deduction_graph_screen.open_deduction_graph(app, card),
        ).pack(side="bottom", pady=(0, 4))

    tk.Label(
        win, text=text, justify="left", wraplength=420, font=theme.body_font(10), bg=theme.bg, anchor="nw"
    ).pack(padx=16, pady=16, anchor="w", fill="both", expand=True)
